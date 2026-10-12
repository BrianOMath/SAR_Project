#!/usr/bin/env python3
"""Met Éireann daily data for Oak Park, and an independently-defined drought window.

Why this exists
---------------
2026's sigma0 VV contrast sits around -5.3 dB through July and August and then
steps to about -3.7 dB from 28 August. If the drought broke in late August, a
test spanning the whole 1 Jul - 30 Sep limb averages the drought together with
its recovery and dilutes exactly what it is looking for.

Narrowing the window BECAUSE the SAR has a step in it would be indefensible --
it is the purest form of choosing a test after seeing the answer, and it would
discredit every careful thing this project has done. The only legitimate way to
narrow it is to define the window from data that knows nothing about the SAR.

Soil moisture deficit does exactly that. It is computed from rainfall and
evapotranspiration by Met Éireann's own model and has no connection to radar.

The discipline this script enforces
-----------------------------------
It writes the derived window to a JSON file BEFORE any SAR test is run, with
the rule that produced it recorded alongside. stratify.py then reads that file.
The window is therefore frozen and auditable: a reader can check that the dates
came from rainfall, not from backscatter.

If the derived window is later changed, that is a new analysis and must be
declared as one.

Source
------
Met Éireann historical daily station data, published under CC BY 4.0. Oak Park,
Co. Carlow is station 375 -- the same station recorded in the AOI GeoJSON.
Daily files for agro-meteorological stations commonly carry soil moisture
deficit for three drainage classes (well / moderately / poorly drained) as well
as rainfall and evapotranspiration, but the column set varies by station and by
period, so this script REPORTS what it finds rather than assuming.

Usage
-----
    python fetch_met.py --station 375 --out ../data/met \\
        --window ../results/phase4/drought_window.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests

# Met Éireann's published daily-data archive. One zip per station.
URL = "https://cli.fusio.net/cli/climate_data/webdata/dly{station}.zip"
TIMEOUT = 120

# Agronomic convention for Irish grassland: a moderately drained soil at a
# deficit beyond ~50 mm is water-limited for growth. Used as the default
# threshold rather than anything tuned to this dataset.
SMD_THRESHOLD_MM = 50.0
MIN_SPELL_DAYS = 10          # a fortnight-ish; shorter dry spells are weather

# Candidate column names, in preference order. Met Éireann uses smd_wd /
# smd_md / smd_pd for well, moderately and poorly drained soils.
SMD_COLUMNS = ("smd_md", "smd_wd", "smd_pd")
RAIN_COLUMNS = ("rain",)


def resolve_local(path: Path) -> Path:
    """The file behind a --local argument, or a message saying why not.

    Windows raises PermissionError when anything opens a directory as a file,
    which reads as a security problem and is nothing of the sort -- it means a
    folder was passed where a file was expected. Left unhandled it sends the
    user hunting through file permissions. So: accept a directory and find the
    data file inside it, and when that is ambiguous say exactly what was found.
    """
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    if path.is_file():
        return path
    if not path.is_dir():
        raise ValueError(f"{path} is neither a file nor a directory")

    seen, uniq = set(), []
    for pat in ("*.zip", "dly*.csv", "*.csv"):
        for c in sorted(path.glob(pat)):
            if c not in seen:
                seen.add(c)
                uniq.append(c)
    if not uniq:
        raise ValueError(
            f"{path} is a directory and contains no .csv or .zip file.\n"
            f"  Point --local at the file you downloaded, for example:\n"
            f"    --local {path / 'dly375.csv'}")
    if len(uniq) > 1:
        listing = "\n".join(f"    {c.name}" for c in uniq[:10])
        raise ValueError(
            f"{path} is a directory holding more than one candidate file:\n"
            f"{listing}\n  Name the one you want with --local.")
    return uniq[0]


def parse_daily(text: str) -> tuple[list[dict], list[str]]:
    """Rows and column names from a Met Éireann daily CSV.

    The files carry a variable-length human-readable preamble before the real
    header, so the header is found by looking for the first line that begins a
    comma-separated field list containing 'date'. Assuming a fixed number of
    preamble lines breaks the moment Met Éireann edits the notes.
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        parts = [p.strip().strip('"').lower() for p in ln.split(",")]
        if parts and parts[0] == "date" and len(parts) > 2:
            start = i
            break
    if start is None:
        raise ValueError("no header row beginning 'date' found in the file")
    cols = [p.strip().strip('"').lower() for p in lines[start].split(",")]
    rows = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[start:])),
                            fieldnames=cols):
        if (r.get("date") or "").strip().lower() == "date":
            continue
        rows.append(r)
    return rows, cols


def to_date(s: str) -> date | None:
    """Met Éireann daily dates are dd-mmm-yyyy; tolerate a couple of variants."""
    s = (s or "").strip().strip('"')
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_float(s) -> float:
    """Blanks and the ' ' / 'n/a' placeholders become NaN rather than zero.

    Treating a missing rainfall day as 0 mm would silently manufacture dry
    weather, which is precisely the variable this script exists to measure.
    """
    try:
        v = str(s).strip().strip('"')
        return float(v) if v not in ("", "n/a", "-", "N/A") else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def pick_column(cols, candidates) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def spells(days: list[date], flag: list[bool],
           min_days: int = MIN_SPELL_DAYS) -> list[tuple[date, date]]:
    """Contiguous runs where `flag` is true, at least `min_days` long."""
    out, start, prev = [], None, None
    for d, f in zip(days, flag):
        if f and start is None:
            start = d
        elif not f and start is not None:
            if (prev - start).days + 1 >= min_days:
                out.append((start, prev))
            start = None
        prev = d
    if start is not None and prev is not None and \
            (prev - start).days + 1 >= min_days:
        out.append((start, prev))
    return out


def longest_spell(sp: list[tuple[date, date]]) -> tuple[date, date] | None:
    return max(sp, key=lambda s: (s[1] - s[0]).days, default=None)


def rainfall_deficit(days, rain, year: int, ref_years) -> dict:
    """Fallback drought index when the station publishes no SMD.

    Cumulative rainfall from 1 April, compared with the same accumulation in the
    reference years. Cruder than SMD -- it ignores evapotranspiration entirely,
    so a hot dry spell and a cool dry spell score alike -- but it is still
    computed without reference to any radar measurement, which is the property
    that matters here.
    """
    def cumulative(y):
        sel = [(d, r) for d, r in zip(days, rain)
               if d.year == y and 4 <= d.month <= 10 and np.isfinite(r)]
        sel.sort()
        if not sel:
            return None
        return [(d, c) for (d, _), c in
                zip(sel, np.cumsum([r for _, r in sel]))]
    target = cumulative(year)
    refs = [cumulative(y) for y in ref_years]
    refs = [r for r in refs if r]
    if not target or not refs:
        return {}
    by_doy = {}
    for r in refs:
        for d, c in r:
            by_doy.setdefault(d.timetuple().tm_yday, []).append(c)
    anomaly = [(d, c - float(np.mean(by_doy.get(d.timetuple().tm_yday, [c]))))
               for d, c in target]
    return {"method": "cumulative rainfall anomaly from 1 April",
            "series": [(d.isoformat(), round(a, 1)) for d, a in anomaly],
            "max_deficit_mm": round(min(a for _, a in anomaly), 1),
            "max_deficit_date": min(anomaly, key=lambda x: x[1])[0].isoformat()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--station", default="375",
                   help="Met Éireann station number (375 = Oak Park)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--window", type=Path, required=True,
                   help="JSON file to freeze the derived drought window into")
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--ref-years", type=int, nargs="+",
                   default=[2021, 2022, 2023, 2024, 2025])
    p.add_argument("--smd-threshold", type=float, default=SMD_THRESHOLD_MM)
    p.add_argument("--local", type=Path,
                   help="use an already-downloaded zip or csv instead")
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    # --- fetch -------------------------------------------------------------
    if args.local:
        try:
            src = resolve_local(args.local)
        except (FileNotFoundError, ValueError) as exc:
            print(f"--local: {exc}")
            return 1
        print(f"reading {src}")
        raw = src.read_bytes()
    else:
        url = URL.format(station=args.station)
        print(f"fetching {url}")
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            raw = r.content
        except requests.RequestException as exc:
            print(f"\nfetch failed: {exc}\n\n"
                  "Met Éireann's archive moves occasionally. Download the daily\n"
                  "file for this station by hand from\n"
                  "  https://www.met.ie/climate/available-data/historical-data\n"
                  "and re-run with --local <path to the zip or csv>.")
            return 1

    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not names:
                print(f"no CSV inside the archive: {z.namelist()}")
                return 1
            print(f"archive contains {names}")
            text = z.read(names[0]).decode("latin-1")
    else:
        text = raw.decode("latin-1")

    rows, cols = parse_daily(text)
    print(f"{len(rows):,} daily records, {len(cols)} columns")
    print(f"columns: {', '.join(cols)}")

    days = [to_date(r.get("date")) for r in rows]
    keep = [i for i, d in enumerate(days) if d is not None]
    days = [days[i] for i in keep]
    rows = [rows[i] for i in keep]
    print(f"record spans {min(days)} to {max(days)}")

    smd_col = pick_column(cols, SMD_COLUMNS)
    rain_col = pick_column(cols, RAIN_COLUMNS)
    print(f"\nsoil moisture deficit column: {smd_col or 'NOT PUBLISHED for this station'}")
    print(f"rainfall column             : {rain_col or 'not found'}")

    # --- daily series out --------------------------------------------------
    wanted = [c for c in (smd_col, rain_col, "maxtp", "mintp", "evap", "pe")
              if c and c in cols]
    daily = args.out / f"met_{args.station}_daily.csv"
    with daily.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + wanted)
        for d, r in zip(days, rows):
            w.writerow([d.isoformat()] + [to_float(r.get(c)) for c in wanted])
    print(f"wrote {daily}")

    # --- derive the window -------------------------------------------------
    window = {"station": args.station, "year": args.year,
              "derived_on": date.today().isoformat(),
              "derived_from": "Met Éireann daily data only; no SAR input"}

    if smd_col:
        sel = [(d, to_float(r.get(smd_col))) for d, r in zip(days, rows)
               if d.year == args.year]
        sel = [(d, v) for d, v in sel if np.isfinite(v)]
        sel.sort()
        if not sel:
            print(f"\nno {smd_col} values for {args.year}")
            return 1
        sp = spells([d for d, _ in sel],
                    [v >= args.smd_threshold for _, v in sel])
        best = longest_spell(sp)
        peak = max(sel, key=lambda x: x[1])
        print(f"\n{args.year} {smd_col}: peak {peak[1]:.1f} mm on {peak[0]}")
        print(f"spells at or above {args.smd_threshold:.0f} mm "
              f"lasting {MIN_SPELL_DAYS}+ days:")
        for a, b in sp:
            print(f"  {a} to {b}   ({(b - a).days + 1} days)")
        for y in args.ref_years:
            rsel = [(d, to_float(r.get(smd_col))) for d, r in zip(days, rows)
                    if d.year == y]
            rsel = [(d, v) for d, v in rsel if np.isfinite(v)]
            if rsel:
                rp = max(rsel, key=lambda x: x[1])
                rs = spells([d for d, _ in rsel],
                            [v >= args.smd_threshold for _, v in rsel])
                tot = sum((b - a).days + 1 for a, b in rs)
                above = sum(1 for _, v in rsel if v >= args.smd_threshold)
                # Two different counts, and conflating them misleads: 2021
                # reaches 60 mm on 22 separate days but never for 10 running,
                # so it contributes 0 days to any qualifying spell. Printing
                # only the second under the label "days above threshold" would
                # have read as "2021 never got dry", which is false.
                print(f"  {y}: peak {rp[1]:>5.1f} mm, {above:>3} days above "
                      f"{args.smd_threshold:.0f} mm, {tot:>3} of them in "
                      f"spells of {MIN_SPELL_DAYS}+ days")
        if best:
            window |= {"method": f"longest spell with {smd_col} >= "
                                 f"{args.smd_threshold:.0f} mm, "
                                 f"minimum {MIN_SPELL_DAYS} days",
                       "variable": smd_col,
                       "threshold_mm": args.smd_threshold,
                       "start": best[0].isoformat(), "end": best[1].isoformat(),
                       "start_doy": best[0].timetuple().tm_yday,
                       "end_doy": best[1].timetuple().tm_yday,
                       "peak_mm": round(peak[1], 1),
                       "peak_date": peak[0].isoformat()}
        else:
            window |= {"method": "no qualifying SMD spell", "start": None}
    elif rain_col:
        rain = [to_float(r.get(rain_col)) for r in rows]
        window |= rainfall_deficit(days, rain, args.year, args.ref_years)
        print("\nNo SMD column at this station. Fell back to a cumulative "
              "rainfall anomaly,\nwhich ignores evapotranspiration -- weaker, "
              "but still independent of the SAR.")
    else:
        print("\nneither SMD nor rainfall found; cannot derive a window")
        return 1

    args.window.parent.mkdir(parents=True, exist_ok=True)
    args.window.write_text(json.dumps(window, indent=2))
    print(f"\nwrote {args.window}")
    if window.get("start"):
        print(f"\nDROUGHT WINDOW: {window['start']} to {window['end']}  "
              f"(DOY {window['start_doy']}-{window['end_doy']})")
        print("This is now frozen. Run the SAR test against it; do not revise "
              "it\nafterwards without declaring a new analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
