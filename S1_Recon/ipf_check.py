"""Report the Sentinel-1 IPF processor version for every processed scene.

Reads Abstracted_Metadata from each SNAP .dim header. The raw products are
deleted after verification (REQ-16), but SNAP copies the original product
metadata into the .dim, so the processor version survives the deletion and this
check can be run at any time after the batch.

Why it matters
--------------
Thermal-noise removal vectors improved across IPF baselines, and the noise
floor correction changed materially at IPF 2.90 (March 2018) and again at 3.10.
A baseline change *inside* a time series would mimic a trend in absolute
backscatter.

It cancels in a same-image spatial contrast -- the identical argument that makes
inter-platform calibration irrelevant to the grassland-minus-forest contrast,
since both strata are measured in the same image with the same noise vectors.
But it affects the absolute sigma0 series, and a project that claims a frozen
configuration has to state which processor versions produced its data.

Usage
-----
    python ipf_check.py C:\\sar\\proc --csv ../results/phase0/ipf_versions.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ATTR = "Processing_system_identifier"

# "ESA SENTINEL-1 IPF 002.84" -> ("002.84", 2.84)
_VERSION = re.compile(r"IPF\s+0*(\d+)\.(\d+)")

# Baselines at which thermal-noise handling changed materially.
NOISE_EPOCHS = (
    (2.90, "annotated noise vectors reworked (Mar 2018)"),
    (3.10, "noise floor re-estimated"),
)


# --------------------------------------------------------------------------
# pure functions
# --------------------------------------------------------------------------

def parse_version(identifier: str) -> tuple[str, float] | tuple[None, None]:
    """Extract the IPF version from a processing-system identifier string.

    Returns (as-written, numeric) so the report can quote the product's own
    text while still sorting and comparing numerically.
    """
    if not identifier:
        return (None, None)
    m = _VERSION.search(identifier)
    if not m:
        return (None, None)
    major, minor = m.group(1), m.group(2)
    return (f"{int(major)}.{minor}", float(f"{int(major)}.{minor}"))


def scene_id(stem: str) -> tuple[str, str]:
    """Split '20260717_S1D' into ('20260717', 'S1D'). Tolerates extra parts."""
    parts = stem.split("_")
    if len(parts) < 2:
        return (stem, "")
    return (parts[0], parts[1])


def crosses_noise_epoch(versions: set[float]) -> list[str]:
    """Which thermal-noise epochs the given version set straddles.

    A series entirely on one side of an epoch is self-consistent. One that
    straddles it has a step change in its noise correction.
    """
    if len(versions) < 2:
        return []
    lo, hi = min(versions), max(versions)
    return [note for cut, note in NOISE_EPOCHS if lo < cut <= hi]


def summarise(rows: list[dict]) -> dict:
    """Group versions by year and flag the series-level problem, if any."""
    by_year: dict[str, set[float]] = defaultdict(set)
    by_version: dict[str, list[str]] = defaultdict(list)
    unknown: list[str] = []

    for r in rows:
        if r["ipf_numeric"] is None:
            unknown.append(r["scene"])
            continue
        by_year[r["date"][:4]].add(r["ipf_numeric"])
        by_version[r["ipf"]].append(r["scene"])

    all_versions = {v for s in by_year.values() for v in s}
    return {
        "by_year": {y: sorted(v) for y, v in sorted(by_year.items())},
        "by_version": {k: sorted(v) for k, v in sorted(by_version.items())},
        "unknown": sorted(unknown),
        "n_versions": len(all_versions),
        "series_epochs": crosses_noise_epoch(all_versions),
        "within_year_mixed": sorted(y for y, v in by_year.items() if len(v) > 1),
    }


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def read_identifier(dim: Path) -> str:
    """Pull Processing_system_identifier out of a .dim header."""
    try:
        tree = ET.parse(dim)
    except (ET.ParseError, OSError) as exc:
        raise RuntimeError(f"{dim.name}: unreadable header ({exc})") from exc

    for el in tree.iter("MDATTR"):
        if el.get("name") == ATTR:
            return (el.text or "").strip()
    return ""


def scan(proc_dir: Path) -> list[dict]:
    rows = []
    for dim in sorted(proc_dir.glob("*.dim")):
        date, platform = scene_id(dim.stem)
        try:
            ident = read_identifier(dim)
        except RuntimeError as exc:
            print(f"  ! {exc}", file=sys.stderr)
            ident = ""
        ipf, numeric = parse_version(ident)
        rows.append({
            "scene": dim.stem,
            "date": date,
            "platform": platform,
            "ipf": ipf or "",
            "ipf_numeric": numeric,
            "identifier": ident,
        })
    return rows


def report(rows: list[dict], summary: dict) -> None:
    print(f"\n{len(rows)} scenes, {summary['n_versions']} distinct IPF versions\n")

    print("by year")
    for year, versions in summary["by_year"].items():
        shown = ", ".join(f"{v:.2f}" for v in versions)
        mark = "  <- mixed" if len(versions) > 1 else ""
        print(f"  {year}  {shown}{mark}")

    print("\nby version")
    for version, scenes in summary["by_version"].items():
        years = sorted({s[:4] for s in scenes})
        print(f"  IPF {version:>6}  {len(scenes):>3} scenes  {', '.join(years)}")

    if summary["unknown"]:
        print(f"\n{len(summary['unknown'])} scenes with no readable version:")
        for s in summary["unknown"][:10]:
            print(f"  {s}")

    print()
    if summary["series_epochs"]:
        print("THE SERIES STRADDLES A THERMAL-NOISE CHANGE:")
        for note in summary["series_epochs"]:
            print(f"  - {note}")
        print("  Cancels in a same-image spatial contrast (both strata share the")
        print("  same noise vectors). Affects the absolute sigma0 series. State it.")
    elif summary["n_versions"] > 1:
        print("Multiple IPF versions, none straddling a thermal-noise epoch.")
    else:
        print("Single IPF version across the whole series.")

    if summary["within_year_mixed"]:
        print(f"\nMixed within a year: {', '.join(summary['within_year_mixed'])}")
        print("  Worth a look -- a within-year step is the case the contrasts")
        print("  protect against but the per-year slope fits cannot.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proc", type=Path, help="directory of processed .dim files")
    ap.add_argument("--csv", type=Path, help="write the per-scene table here")
    args = ap.parse_args()

    if not args.proc.is_dir():
        raise SystemExit(f"not a directory: {args.proc}")

    rows = scan(args.proc)
    if not rows:
        raise SystemExit(f"no .dim files in {args.proc}")

    summary = summarise(rows)
    report(rows, summary)

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "scene", "date", "platform", "ipf", "identifier"])
            w.writeheader()
            for r in rows:
                w.writerow({k: r[k] for k in w.fieldnames})
        print(f"\nwrote {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
