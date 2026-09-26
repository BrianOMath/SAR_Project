#!/usr/bin/env python3
"""Download, process and verify a Sentinel-1 batch, one scene at a time.

Phase 2 of the SAR drought project. Reads the scene list produced by
`s1_recon.py`, and for each acquisition:

    download -> gpt (SNAP graph) -> verify_scene -> delete the raw product

Raw products are deleted ONLY after the output has been verified, so a
failure never costs you the input. Download runs one scene ahead of
processing in a background thread, because download is the slow half
(~2.6 h against ~1 h of compute for the full batch) and the two overlap
almost perfectly. A bounded queue keeps peak disk to two or three raw
products rather than the whole 145 GB.

Resumable: a scene already present in the manifest as verified is skipped.
Kill it and restart and it picks up where it stopped.

Credentials come from the environment, never the command line:

    $env:CDSE_USER     = "you@example.com"
    $env:CDSE_PASSWORD = "..."

Usage
-----
    # the four cross-calibration scenes (REQ-09), as a smoke test
    python batch_process.py --scenes recon_out/scenes.csv \\
        --graph ../graphs/s1_grd_preprocess_v2.xml --aoi aoi_oakpark.geojson \\
        --out C:/sar/proc --raw C:/sar/raw \\
        --dates 2026-04-23 2026-04-24 2026-06-28 2026-06-29

    # the full batch
    python batch_process.py --scenes recon_out/scenes.csv \\
        --graph ../graphs/s1_grd_preprocess_v2.xml --aoi aoi_oakpark.geojson \\
        --out C:/sar/proc --raw C:/sar/raw --years 2024 2025 2026

    python batch_process.py ... --dry-run     # plan only, touch nothing
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import requests

TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
             "/protocol/openid-connect/token")
CLIENT_ID = "cdse-public"
DOWNLOAD_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({pid})/$value"

PREFETCH = 1          # raw products downloaded ahead of the processor
MIN_FREE_GB = 12.0    # refuse to start a download below this


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------

@dataclass
class Job:
    """One acquisition to process."""
    date: str
    platform: str
    product_id: str
    name: str
    size_bytes: int
    relative_orbit: int
    orbit_direction: str

    @property
    def stem(self) -> str:
        return f"{self.date.replace('-', '')}_{self.platform}"


@dataclass
class Result:
    date: str
    platform: str
    stem: str
    status: str            # verified | gpt_failed | verify_failed | download_failed | skipped
    detail: str = ""
    download_s: float = 0.0
    process_s: float = 0.0
    product_id: str = ""
    finished: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --------------------------------------------------------------------------
# pure: scene selection
# --------------------------------------------------------------------------

def read_scenes(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_jobs(rows: Iterable[dict],
               relative_orbit: int,
               orbit_direction: str,
               years: Sequence[int] | None = None,
               dates: Sequence[str] | None = None,
               months: tuple[int, int] | None = (4, 10)) -> tuple[list[Job], list[Result]]:
    """Select acquisitions and return (jobs, exclusions).

    Products are grouped by date. An acquisition that arrived as more than one
    GRD slice is EXCLUDED and the exclusion recorded, per REQ-17 — mosaicking
    is not implemented, and silently processing one slice of two would be the
    worst of the available options.
    """
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        if int(r["relative_orbit"]) != relative_orbit:
            continue
        if r["orbit_direction"].upper() != orbit_direction.upper():
            continue
        day = r["start"][:10]
        if dates and day not in set(dates):
            continue
        if years and int(day[:4]) not in set(years):
            continue
        if months and not (months[0] <= int(day[5:7]) <= months[1]):
            continue
        by_date.setdefault(day, []).append(r)

    jobs: list[Job] = []
    excluded: list[Result] = []
    for day in sorted(by_date):
        group = by_date[day]
        plat = group[0]["platform"]
        if len(group) > 1:
            excluded.append(Result(
                date=day, platform=plat, stem=f"{day.replace('-', '')}_{plat}",
                status="skipped",
                detail=f"{len(group)} GRD slices on this date; mosaicking not "
                       f"implemented, excluded per REQ-17"))
            continue
        r = group[0]
        jobs.append(Job(
            date=day, platform=plat, product_id=r["product_id"], name=r["name"],
            size_bytes=int(r["size_bytes"]), relative_orbit=int(r["relative_orbit"]),
            orbit_direction=r["orbit_direction"]))
    return jobs, excluded


def already_done(manifest_rows: Iterable[dict]) -> set[str]:
    """Stems that completed verification in an earlier run."""
    return {r["stem"] for r in manifest_rows if r.get("status") == "verified"}


def plan(jobs: Sequence[Job], done: set[str]) -> tuple[list[Job], list[Job]]:
    """Split into (to_run, to_skip) without touching the filesystem."""
    todo = [j for j in jobs if j.stem not in done]
    skip = [j for j in jobs if j.stem in done]
    return todo, skip


def total_gb(jobs: Sequence[Job]) -> float:
    return sum(j.size_bytes for j in jobs) / 1e9


# --------------------------------------------------------------------------
# pure: token lifetime
# --------------------------------------------------------------------------

def token_expired(issued_at: float, expires_in: float, now: float,
                  margin_s: float = 60.0) -> bool:
    """True when the access token is within `margin_s` of expiry.

    CDSE access tokens live about 10 minutes; a full batch runs for hours, so
    a token fetched once at the start would fail partway through.
    """
    return now >= issued_at + expires_in - margin_s


# --------------------------------------------------------------------------
# I/O: CDSE auth and download
# --------------------------------------------------------------------------

class Cdse:
    """Access token with refresh. Credentials are read from the environment."""

    def __init__(self, session: requests.Session | None = None):
        self.user = os.environ.get("CDSE_USER")
        self.password = os.environ.get("CDSE_PASSWORD")
        if not self.user or not self.password:
            raise SystemExit(
                "set CDSE_USER and CDSE_PASSWORD in the environment "
                "(never on the command line — it lands in shell history)")
        self.s = session or requests.Session()
        self._token = ""
        self._refresh = ""
        self._issued = 0.0
        self._expires = 0.0

    def _post(self, data: dict) -> None:
        r = self.s.post(TOKEN_URL, data=data, timeout=60)
        r.raise_for_status()
        p = r.json()
        self._token = p["access_token"]
        self._refresh = p.get("refresh_token", "")
        self._expires = float(p.get("expires_in", 600))
        self._issued = time.time()

    def token(self) -> str:
        if self._token and not token_expired(self._issued, self._expires, time.time()):
            return self._token
        if self._refresh:
            try:
                self._post({"grant_type": "refresh_token",
                            "refresh_token": self._refresh,
                            "client_id": CLIENT_ID})
                return self._token
            except requests.RequestException:
                pass          # refresh window gone; fall through to full auth
        self._post({"grant_type": "password", "username": self.user,
                    "password": self.password, "client_id": CLIENT_ID})
        return self._token


def download_product(cdse: Cdse, product_id: str, dest: Path,
                     max_retries: int = 3) -> float:
    """Stream one product to `dest`. Returns elapsed seconds.

    requests drops the Authorization header on a cross-host redirect, and CDSE
    redirects downloads to a separate host — so redirects are followed by hand
    with the bearer token re-attached.
    """
    url = DOWNLOAD_URL.format(pid=product_id)
    tmp = dest.with_suffix(dest.suffix + ".part")
    t0 = time.time()

    for attempt in range(max_retries):
        try:
            headers = {"Authorization": f"Bearer {cdse.token()}"}
            r = cdse.s.get(url, headers=headers, stream=True,
                           allow_redirects=False, timeout=120)
            hops = 0
            while r.status_code in (301, 302, 303, 307, 308) and hops < 10:
                nxt = r.headers["Location"]
                r.close()
                r = cdse.s.get(nxt, headers=headers, stream=True,
                               allow_redirects=False, timeout=120)
                hops += 1
            r.raise_for_status()

            with tmp.open("wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
            r.close()
            tmp.replace(dest)
            return time.time() - t0
        except (requests.RequestException, OSError) as exc:
            tmp.unlink(missing_ok=True)
            if attempt == max_retries - 1:
                raise
            wait = 5 * 2 ** attempt
            print(f"    download retry {attempt + 1}/{max_retries} in {wait}s ({exc})",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


# --------------------------------------------------------------------------
# I/O: processing and verification
# --------------------------------------------------------------------------

def gpt_error(stdout: str, stderr: str) -> str:
    """Extract the useful line from gpt output.

    Java prints the message FIRST and the stack trace after it, so taking the
    last line of stderr yields `at com.install4j...WinLauncher.main(...)` —
    true, and completely useless. Prefer the first real error line.
    """
    for stream in (stderr, stdout):
        for line in stream.splitlines():
            s = line.strip()
            if not s or s.startswith(("INFO:", "WARNING:", "at ", "Caused by:")):
                continue
            if s.startswith("Error:") or "Exception" in s or "Error" in s:
                return s
    # nothing matched: fall back to the first substantive line
    for stream in (stderr, stdout):
        for line in stream.splitlines():
            s = line.strip()
            if s and not s.startswith(("INFO:", "WARNING:", "at ")):
                return s
    return "no diagnostic output"


def preflight(gpt: Path, graph: Path, aoi: Path,
              check_import: bool = True) -> list[str]:
    """Everything that must be true before a single byte is downloaded.

    A missing file costs nothing to detect and minutes of downloading to
    discover the hard way. Ask first — including whether the verify module
    can actually be imported, because that import happens per scene, after
    the download and after gpt.
    """
    problems = []
    if not graph.is_file():
        problems.append(f"graph not found: {graph.resolve()}")
    if not aoi.is_file():
        problems.append(f"AOI not found: {aoi.resolve()}")
    if not gpt.is_file():
        problems.append(f"gpt not found: {gpt}")
    if check_import:
        problems.extend(import_problem())
    return problems


def listed_in_requirements(module: str, req: Path) -> bool | None:
    """Is `module` named in requirements.txt? None if the file is unreadable.

    Distribution and import names differ in general; for this project's
    dependencies they match, so a simple prefix comparison is honest enough.
    """
    try:
        text = req.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name = line.split("[")[0]
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "="):
            name = name.split(sep)[0]
        if name.strip().lower().replace("-", "_") == module.lower().replace("-", "_"):
            return True
    return False


def import_problem(req: Path | None = None) -> list[str]:
    """Check verify_scene imports, and say WHICH thing is missing.

    An ImportError here has two quite different causes and two different
    fixes, so do not guess: `exc.name` is the module that actually failed.
    Reporting "it must sit beside batch_process.py" when the real problem
    was an uninstalled rasterio sent the reader to the wrong place.
    """
    try:
        import verify_scene  # noqa: F401
        return []
    except ImportError as exc:
        missing = getattr(exc, "name", None) or ""
        if missing == "verify_scene":
            return [f"cannot import verify_scene — it must sit beside "
                    f"batch_process.py in {Path(__file__).parent.resolve()}"]
        req = req or Path(__file__).parent / "requirements.txt"
        listed = listed_in_requirements(missing, req)
        if listed is False:
            # Telling someone to run a command they have already run, against
            # a file that does not mention the package, is a loop. Say so.
            return [f"verify_scene needs '{missing}', which is not installed in "
                    f"{sys.executable} — and '{missing}' is NOT listed in "
                    f"{req.resolve()}. That file is out of date; update it, "
                    f"then: python -m pip install -r requirements.txt"]
        return [f"verify_scene needs '{missing}', which is not installed in "
                f"{sys.executable} — run: python -m pip install -r requirements.txt"]


def run_gpt(gpt: Path, graph: Path, src: Path, dst: Path,
            cache: str, threads: int, log: Path) -> tuple[bool, str]:
    cmd = [str(gpt), str(graph), f"-Pinput={src}", f"-Poutput={dst}",
           "-c", cache, "-q", str(threads)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log.write_text(
        f"$ {' '.join(cmd)}\n\n--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}\n", encoding="utf-8")
    if proc.returncode != 0:
        return False, f"gpt exit {proc.returncode}: {gpt_error(proc.stdout, proc.stderr)[:200]}"
    return True, f"{time.time() - t0:.0f}s"


def verify(dim: Path, aoi: Path, log: Path) -> tuple[bool, str]:
    """Run the scene checker and capture its report.

    Imported rather than shelled out so the batch gate is literally the same
    code as the interactive check — one definition of 'good', not two.
    """
    buf = io.StringIO()
    try:
        import verify_scene          # inside the try: a bad import fails ONE
        with redirect_stdout(buf):   # scene, it does not kill the batch
            rc = verify_scene.main([str(dim), "--aoi", str(aoi)])
    except SystemExit as exc:
        rc, = (exc.code or 0,) if not isinstance(exc.code, str) else (1,)
        buf.write(f"\n{exc}\n")
    except (Exception, ImportError) as exc:       # noqa: BLE001 - log, fail the scene
        rc = 1
        buf.write(f"\nverify raised {type(exc).__name__}: {exc}\n")

    text = buf.getvalue()
    log.write_text(text, encoding="utf-8")
    if rc == 0:
        return True, "all hard checks passed"
    fails = [l.strip() for l in text.splitlines() if "[FAIL]" in l]
    return False, "; ".join(f[:80] for f in fails[:3]) or "verify returned non-zero"


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

MANIFEST_COLS = [f.name for f in fields(Result)]


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_manifest(path: Path, result: Result) -> None:
    """Append immediately, so a crash keeps everything already done."""
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLS)
        if new:
            w.writeheader()
        w.writerow(asdict(result))


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

def downloader(jobs: Sequence[Job], raw_dir: Path, q: "queue.Queue",
               cdse: Cdse, stop: threading.Event) -> None:
    """Producer: keeps PREFETCH raw products ready for the processor."""
    for job in jobs:
        if stop.is_set():
            break
        # removesuffix, NOT rstrip: rstrip removes any trailing characters in
        # the set {'.','S','A','F','E'}, so a product ending ..._702F.SAFE
        # loses its final F. That is a real product id in this batch.
        dest = raw_dir / f"{job.name.removesuffix('.SAFE')}.zip"
        try:
            if dest.exists() and dest.stat().st_size == job.size_bytes:
                q.put((job, dest, 0.0, None))     # already on disk from a prior run
                continue
            need = job.size_bytes / 1e9 * 2.5
            while free_gb(raw_dir) < max(MIN_FREE_GB, need) and not stop.is_set():
                time.sleep(20)                    # wait for the processor to free space
            secs = download_product(cdse, job.product_id, dest)
            q.put((job, dest, secs, None))
        except Exception as exc:                  # noqa: BLE001
            q.put((job, None, 0.0, exc))
    q.put(None)                                   # sentinel


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenes", type=Path, required=True, help="scenes.csv from s1_recon")
    p.add_argument("--graph", type=Path, required=True, help="SNAP graph XML")
    p.add_argument("--aoi", type=Path, required=True, help="AOI GeoJSON")
    p.add_argument("--out", type=Path, required=True, help="processed output directory")
    p.add_argument("--raw", type=Path, required=True, help="raw download directory")
    p.add_argument("--gpt", type=Path,
                   default=Path(r"C:\Program Files\esa-snap\bin\gpt.exe"))
    p.add_argument("--relative-orbit", type=int, default=1)
    p.add_argument("--orbit-direction", default="ASCENDING")
    p.add_argument("--years", type=int, nargs="+")
    p.add_argument("--dates", nargs="+", help="explicit YYYY-MM-DD list")
    p.add_argument("--months", type=int, nargs=2, default=[4, 10])
    p.add_argument("--all-months", action="store_true")
    p.add_argument("--cache", default="8G", help="gpt tile cache")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--keep-raw", action="store_true", help="do not delete inputs")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    months = None if args.all_months else tuple(args.months)
    rows = read_scenes(args.scenes)
    jobs, excluded = build_jobs(rows, args.relative_orbit, args.orbit_direction,
                                args.years, args.dates, months)

    problems = preflight(args.gpt, args.graph, args.aoi)
    if problems:
        print("preflight failed — nothing downloaded:", file=sys.stderr)
        for pb in problems:
            print(f"  {pb}", file=sys.stderr)
        return 2

    manifest = args.out / "manifest.csv"
    done = already_done(read_manifest(manifest))
    todo, skip = plan(jobs, done)

    print(f"selected   : orbit {args.relative_orbit} {args.orbit_direction}")
    print(f"acquisitions: {len(jobs)}  ({len(skip)} already verified, "
          f"{len(todo)} to run)")
    if excluded:
        print(f"excluded   : {len(excluded)} multi-slice acquisitions (REQ-17)")
        for e in excluded:
            print(f"             {e.date} {e.platform} — {e.detail}")
    print(f"download   : {total_gb(todo):.0f} GB")
    print(f"estimate   : ~{len(todo) * 0.8:.0f} min of processing\n")

    if args.dry_run:
        for j in todo[:10]:
            print(f"  would run {j.stem}  {j.name[:60]}")
        if len(todo) > 10:
            print(f"  ... and {len(todo) - 10} more")
        return 0
    if not todo:
        print("nothing to do")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    args.raw.mkdir(parents=True, exist_ok=True)
    (args.out / "logs").mkdir(exist_ok=True)
    for e in excluded:
        if e.stem not in done:
            append_manifest(manifest, e)

    cdse = Cdse()
    q: "queue.Queue" = queue.Queue(maxsize=PREFETCH)
    stop = threading.Event()
    t = threading.Thread(target=downloader, args=(todo, args.raw, q, cdse, stop),
                         daemon=True)
    t.start()

    n_ok = n_fail = 0
    t_start = time.time()
    try:
        while True:
            item = q.get()
            if item is None:
                break
            job, src, dl_s, err = item
            print(f"[{n_ok + n_fail + 1}/{len(todo)}] {job.stem}", end="  ", flush=True)

            if err is not None:
                res = Result(job.date, job.platform, job.stem, "download_failed",
                             str(err)[:200], dl_s, 0.0, job.product_id)
                print(f"DOWNLOAD FAILED — {err}")
                append_manifest(manifest, res); n_fail += 1
                continue

            dim = args.out / f"{job.stem}.dim"
            t0 = time.time()
            ok, detail = run_gpt(args.gpt, args.graph, src, dim, args.cache,
                                 args.threads, args.out / "logs" / f"{job.stem}.gpt.log")
            proc_s = time.time() - t0

            if not ok:
                print(f"GPT FAILED — {detail}")
                append_manifest(manifest, Result(job.date, job.platform, job.stem,
                                                 "gpt_failed", detail, dl_s, proc_s,
                                                 job.product_id))
                n_fail += 1
                continue

            vok, vdetail = verify(dim, args.aoi,
                                  args.out / "logs" / f"{job.stem}.verify.log")
            status = "verified" if vok else "verify_failed"
            append_manifest(manifest, Result(job.date, job.platform, job.stem, status,
                                             vdetail, dl_s, proc_s, job.product_id))

            if vok:
                # Raw is deleted only now: after processing AND verification.
                if not args.keep_raw:
                    src.unlink(missing_ok=True)
                print(f"ok  dl {dl_s:5.0f}s  proc {proc_s:4.0f}s")
                n_ok += 1
            else:
                print(f"VERIFY FAILED — {vdetail}  (raw kept)")
                n_fail += 1
    except KeyboardInterrupt:
        stop.set()
        print("\ninterrupted — manifest is current, rerun to resume")
        return 130

    mins = (time.time() - t_start) / 60
    print(f"\n{n_ok} verified, {n_fail} failed, {len(skip)} skipped  "
          f"in {mins:.0f} min")
    print(f"manifest: {manifest}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
