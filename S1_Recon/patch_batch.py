"""Apply the slice-assembly changes to batch_process.py.

Every replacement is anchored on exact existing text and asserted to match
once. If any anchor fails, nothing is written -- the file is left as it was
and the failing anchor is named.

Usage:
    python patch_batch.py <path to batch_process.py>
"""

from __future__ import annotations

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# R1  imports
# --------------------------------------------------------------------------

R1_OLD = """from typing import Iterable, Sequence

import requests
"""

R1_NEW = """from typing import Iterable, Sequence
import xml.etree.ElementTree as ET
import zipfile

import requests

import slices
from s1_recon import load_aoi
"""

# --------------------------------------------------------------------------
# R2  Job gains a product list
# --------------------------------------------------------------------------

R2_OLD = '''@dataclass
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
'''

R2_NEW = '''@dataclass
class Product:
    """One catalogue product: a single GRD slice."""
    product_id: str
    name: str
    size_bytes: int


@dataclass
class Job:
    """One acquisition to process: one product, or several to be assembled.

    On relative orbit 1 the AOI sits inside a single slice throughout
    2021-2026 but straddles a slice boundary from 2016 to mid-2020, where the
    best single slice covers 0.8232 of it. 121 of the 316 acquisitions need
    two slices assembled; the rest are a single product, processed by exactly
    the path that produced the existing results.

    product_id, name and size_bytes stay available as properties so the
    manifest columns and the disk-space arithmetic do not change shape.
    """
    date: str
    platform: str
    relative_orbit: int
    orbit_direction: str
    action: str                 # 'single' | 'assemble'
    products: list[Product]

    @property
    def stem(self) -> str:
        return f"{self.date.replace('-', '')}_{self.platform}"

    @property
    def size_bytes(self) -> int:
        return sum(p.size_bytes for p in self.products)

    @property
    def product_id(self) -> str:
        """Every product behind this acquisition, so the manifest records
        exactly what was used. Comma-separated for an assembly."""
        return ",".join(p.product_id for p in self.products)

    @property
    def name(self) -> str:
        return self.products[0].name
'''

# --------------------------------------------------------------------------
# R3  build_jobs delegates to slices.plan_acquisition
# --------------------------------------------------------------------------

R3_OLD = '''def build_jobs(rows: Iterable[dict],
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
'''

R3_NEW = '''def build_jobs(rows: Iterable[dict],
               relative_orbit: int,
               orbit_direction: str,
               aoi,
               years: Sequence[int] | None = None,
               dates: Sequence[str] | None = None,
               months: tuple[int, int] | None = (4, 10)) -> tuple[list[Job], list[Result]]:
    """Select acquisitions and return (jobs, exclusions).

    Products are grouped by date and each date is planned by
    `slices.plan_acquisition`, which de-duplicates the catalogue, keeps only
    the slices touching the AOI, prefers a single slice wherever one covers
    the AOI alone, and validates anything it proposes to assemble.

    This replaces REQ-17's blanket exclusion of multi-slice dates. That rule
    was correct while mosaicking did not exist -- processing one slice of two
    would have put a partial footprint into the series invisibly -- but it
    removed every acquisition in 2018, 2019 and 2020, which is to say the
    whole confirmatory test. Exclusions are still possible and still recorded;
    they are now specific, and `plan_acquisition` says why.
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
        stem = f"{day.replace('-', '')}_{plat}"
        planned = slices.plan_acquisition(group, aoi)

        if planned["action"] == "exclude":
            excluded.append(Result(
                date=day, platform=plat, stem=stem, status="skipped",
                detail=planned["reason"]))
            continue

        jobs.append(Job(
            date=day, platform=plat,
            relative_orbit=int(group[0]["relative_orbit"]),
            orbit_direction=group[0]["orbit_direction"],
            action=planned["action"],
            products=[Product(product_id=r["product_id"], name=r["name"],
                              size_bytes=int(r["size_bytes"]))
                      for r in planned["products"]]))
    return jobs, excluded
'''

# --------------------------------------------------------------------------
# R4  assembly I/O, inserted before verify()
# --------------------------------------------------------------------------

R4_OLD = '''def verify(dim: Path, aoi: Path, log: Path) -> tuple[bool, str]:
'''

R4_NEW = '''def ipf_from_safe(zip_path: Path) -> str:
    """The IPF processor version from a downloaded SAFE zip, or "" if unreadable.

    Read from manifest.safe rather than the catalogue, because this is the
    version of the bytes actually on disk. Returns "" rather than raising: a
    missing version is reported by `slices.ipf_consistent` alongside whatever
    else it finds, instead of aborting mid-batch.
    """
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = [n for n in z.namelist() if n.endswith("manifest.safe")]
            if not names:
                return ""
            with z.open(sorted(names, key=len)[0]) as fh:
                root = ET.parse(fh).getroot()
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        return ""

    # <safe:software name="Sentinel-1 IPF" version="002.84"/>, namespaced.
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != "software":
            continue
        version = el.get("version") or ""
        if version and "IPF" in (el.get("name") or "IPF"):
            return version
    return ""


def run_assembly(gpt: Path, srcs: Sequence[Path], dst: Path,
                 cache: str, threads: int, log: Path) -> tuple[bool, str]:
    """Concatenate consecutive GRD slices into one product.

    SliceAssembly works in slant-range geometry, BEFORE terrain correction, so
    the assembled product is geocoded in a single pass and lands on the shared
    10 m lattice like any other scene. SNAP's Mosaic operator would resample
    products already geocoded, which is exactly how NCR-12 would come back --
    and NCR-12's fix is what makes pixel n the same patch of Carlow in every
    scene in the stack.

    Sources are passed in acquisition order; `slices.assembly_order` sorts
    them and `slices.assembly_problems` has already checked they are
    contiguous, share a datatake and a platform, and cover the AOI.
    """
    cmd = [str(gpt), "SliceAssembly",
           "-PselectedPolarisations=VV,VH",
           "-t", str(dst), "-f", "BEAM-DIMAP",
           "-c", cache, "-q", str(threads),
           *[str(s) for s in srcs]]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log.write_text(
        f"$ {' '.join(cmd)}\\n\\n--- stdout ---\\n{proc.stdout}\\n"
        f"--- stderr ---\\n{proc.stderr}\\n", encoding="utf-8")
    if proc.returncode != 0:
        return False, (f"SliceAssembly exit {proc.returncode}: "
                       f"{gpt_error(proc.stdout, proc.stderr)[:200]}")
    if not dst.exists():
        return False, "SliceAssembly reported success but wrote no product"
    return True, f"{time.time() - t0:.0f}s"


def discard_assembly(dim: Path) -> None:
    """Remove an assembled intermediate and its .data directory.

    These are full-swath products of several GB. Left behind, a 121-assembly
    batch would fill the disk long before it finished.
    """
    shutil.rmtree(dim.with_suffix(".data"), ignore_errors=True)
    dim.unlink(missing_ok=True)


def verify(dim: Path, aoi: Path, log: Path) -> tuple[bool, str]:
'''

# --------------------------------------------------------------------------
# R5  downloader fetches every product of a job
# --------------------------------------------------------------------------

R5_OLD = '''    for job in jobs:
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
'''

R5_NEW = '''    for job in jobs:
        if stop.is_set():
            break
        try:
            paths: list[Path] = []
            secs = 0.0
            for prod in job.products:
                # removesuffix, NOT rstrip: rstrip removes any trailing
                # characters in the set {'.','S','A','F','E'}, so a product
                # ending ..._702F.SAFE loses its final F. That is a real
                # product id in this batch.
                dest = raw_dir / f"{prod.name.removesuffix('.SAFE')}.zip"
                if dest.exists() and dest.stat().st_size == prod.size_bytes:
                    paths.append(dest)            # already on disk from a prior run
                    continue
                # Headroom for every slice of this acquisition plus the
                # assembled intermediate, which is as large as the slices
                # together.
                need = job.size_bytes / 1e9 * 2.5
                while free_gb(raw_dir) < max(MIN_FREE_GB, need) and not stop.is_set():
                    time.sleep(20)                # wait for the processor to free space
                secs += download_product(cdse, prod.product_id, dest)
                paths.append(dest)
            q.put((job, paths, secs, None))
        except Exception as exc:                  # noqa: BLE001
            q.put((job, None, 0.0, exc))
    q.put(None)                                   # sentinel
'''

# --------------------------------------------------------------------------
# R6  new CLI options
# --------------------------------------------------------------------------

R6_OLD = '''    p.add_argument("--graph", type=Path, required=True, help="SNAP graph XML")
'''

R6_NEW = '''    p.add_argument("--graph", type=Path, required=True,
                   help="SNAP graph for single-slice acquisitions (v3)")
    p.add_argument("--graph-assembled", type=Path,
                   help="SNAP graph for assembled acquisitions (v4: v3 with the "
                        "Read formatName removed). Defaults to --graph with "
                        "v3 replaced by v4.")
    p.add_argument("--allow-mixed-ipf", action="store_true",
                   help="assemble slices processed on different IPF baselines. "
                        "Off by default: a baseline difference puts a "
                        "radiometric step at the seam, and that only cancels "
                        "in a spatial contrast if every stratum is spread "
                        "evenly across the boundary.")
'''

# --------------------------------------------------------------------------
# R7  main: resolve the second graph, load the AOI, pass it to build_jobs
# --------------------------------------------------------------------------

R7_OLD = '''    months = None if args.all_months else tuple(args.months)
    rows = read_scenes(args.scenes)
    jobs, excluded = build_jobs(rows, args.relative_orbit, args.orbit_direction,
                                args.years, args.dates, months)
'''

R7_NEW = '''    months = None if args.all_months else tuple(args.months)
    if args.graph_assembled is None:
        args.graph_assembled = args.graph.with_name(
            args.graph.name.replace("v3", "v4"))

    rows = read_scenes(args.scenes)
    aoi = load_aoi(args.aoi)
    jobs, excluded = build_jobs(rows, args.relative_orbit, args.orbit_direction,
                                aoi, args.years, args.dates, months)
    n_asm = sum(1 for j in jobs if j.action == "assemble")
'''

# --------------------------------------------------------------------------
# R8  preflight the second graph too
# --------------------------------------------------------------------------

R8_OLD = '''    problems = preflight(args.gpt, args.graph, args.aoi)
    if problems:
'''

R8_NEW = '''    problems = preflight(args.gpt, args.graph, args.aoi)
    if n_asm and not args.graph_assembled.is_file():
        problems.append(f"{n_asm} acquisitions need assembly but the assembled "
                        f"graph is missing: {args.graph_assembled}")
    if problems:
'''

# --------------------------------------------------------------------------
# R9  reporting
# --------------------------------------------------------------------------

R9_OLD = '''    if excluded:
        print(f"excluded   : {len(excluded)} multi-slice acquisitions (REQ-17)")
        for e in excluded:
            print(f"             {e.date} {e.platform} — {e.detail}")
'''

R9_NEW = '''    n_asm_todo = sum(1 for j in todo if j.action == "assemble")
    if n_asm_todo:
        print(f"assembly   : {n_asm_todo} of {len(todo)} need slices assembled "
              f"({args.graph_assembled.name})")
    if excluded:
        print(f"excluded   : {len(excluded)} acquisitions")
        for e in excluded:
            print(f"             {e.date} {e.platform} — {e.detail}")
'''

# --------------------------------------------------------------------------
# R10  dry-run shows the action and slice count
# --------------------------------------------------------------------------

R10_OLD = '''        for j in todo[:10]:
            print(f"  would run {j.stem}  {j.name[:60]}")
'''

R10_NEW = '''        for j in todo[:10]:
            how = (f"assemble {len(j.products)}" if j.action == "assemble"
                   else "single     ")
            print(f"  would run {j.stem}  {how}  {j.name[:52]}")
'''

# --------------------------------------------------------------------------
# R11  the processing step: assemble when needed, then the usual graph
# --------------------------------------------------------------------------

R11_OLD = '''            dim = args.out / f"{job.stem}.dim"
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
'''

R11_NEW = '''            dim = args.out / f"{job.stem}.dim"
            logs = args.out / "logs"
            t0 = time.time()
            assembled: Path | None = None
            graph, gpt_src = args.graph, src[0]

            if job.action == "assemble":
                # The seam check, before anything is welded together.
                versions = {p.name: ipf_from_safe(s)
                            for p, s in zip(job.products, src)}
                ipf_problems = slices.ipf_consistent(versions)
                if ipf_problems and not args.allow_mixed_ipf:
                    detail = "; ".join(ipf_problems)[:200]
                    print(f"IPF MISMATCH — {detail}  (raw kept)")
                    append_manifest(manifest, Result(
                        job.date, job.platform, job.stem, "gpt_failed",
                        detail, dl_s, time.time() - t0, job.product_id))
                    n_fail += 1
                    continue
                if ipf_problems:
                    print(f"\\n    WARNING, proceeding under --allow-mixed-ipf: "
                          f"{'; '.join(ipf_problems)}")

                assembled = args.raw / f"{job.stem}_assembled.dim"
                aok, adetail = run_assembly(
                    args.gpt, src, assembled, args.cache, args.threads,
                    logs / f"{job.stem}.assembly.log")
                if not aok:
                    discard_assembly(assembled)
                    print(f"ASSEMBLY FAILED — {adetail}")
                    append_manifest(manifest, Result(
                        job.date, job.platform, job.stem, "gpt_failed",
                        adetail, dl_s, time.time() - t0, job.product_id))
                    n_fail += 1
                    continue
                graph, gpt_src = args.graph_assembled, assembled

            ok, detail = run_gpt(args.gpt, graph, gpt_src, dim, args.cache,
                                 args.threads, logs / f"{job.stem}.gpt.log")
            if assembled is not None:
                discard_assembly(assembled)
            proc_s = time.time() - t0

            if job.action == "assemble":
                ipf = sorted({v for v in versions.values() if v})
                detail = f"assembled {len(job.products)} slices, IPF " \\
                         f"{','.join(ipf) or 'unknown'}; {detail}"

            if not ok:
                print(f"GPT FAILED — {detail}")
                append_manifest(manifest, Result(job.date, job.platform, job.stem,
                                                 "gpt_failed", detail, dl_s, proc_s,
                                                 job.product_id))
                n_fail += 1
                continue
'''

# --------------------------------------------------------------------------
# R12  verification detail keeps the assembly note; raw deletion loops
# --------------------------------------------------------------------------

R12_OLD = '''            vok, vdetail = verify(dim, args.aoi,
                                  args.out / "logs" / f"{job.stem}.verify.log")
            status = "verified" if vok else "verify_failed"
            append_manifest(manifest, Result(job.date, job.platform, job.stem, status,
                                             vdetail, dl_s, proc_s, job.product_id))

            if vok:
                # Raw is deleted only now: after processing AND verification.
                if not args.keep_raw:
                    src.unlink(missing_ok=True)
'''

R12_NEW = '''            vok, vdetail = verify(dim, args.aoi,
                                  logs / f"{job.stem}.verify.log")
            status = "verified" if vok else "verify_failed"
            if job.action == "assemble":
                vdetail = f"{detail} | {vdetail}"
            append_manifest(manifest, Result(job.date, job.platform, job.stem, status,
                                             vdetail, dl_s, proc_s, job.product_id))

            if vok:
                # Raw is deleted only now: after processing AND verification.
                if not args.keep_raw:
                    for s in src:
                        s.unlink(missing_ok=True)
'''

REPLACEMENTS = [
    ("R1 imports", R1_OLD, R1_NEW),
    ("R2 Job/Product", R2_OLD, R2_NEW),
    ("R3 build_jobs", R3_OLD, R3_NEW),
    ("R4 assembly I/O", R4_OLD, R4_NEW),
    ("R5 downloader", R5_OLD, R5_NEW),
    ("R6 CLI options", R6_OLD, R6_NEW),
    ("R7 main wiring", R7_OLD, R7_NEW),
    ("R8 preflight", R8_OLD, R8_NEW),
    ("R9 reporting", R9_OLD, R9_NEW),
    ("R10 dry run", R10_OLD, R10_NEW),
    ("R11 processing", R11_OLD, R11_NEW),
    ("R12 verify/cleanup", R12_OLD, R12_NEW),
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    text = original = path.read_text(encoding="utf-8")

    failures = []
    for label, old, new in REPLACEMENTS:
        n = text.count(old)
        if n != 1:
            failures.append(f"{label}: anchor matched {n} times, expected 1")
            continue
        text = text.replace(old, new, 1)

    if failures:
        print("PATCH NOT APPLIED — file unchanged:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    import ast
    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"PATCH NOT APPLIED — result would not parse: {exc}", file=sys.stderr)
        return 1

    backup = path.with_suffix(".py.pre-assembly")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"backup: {backup.name}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name}: {len(REPLACEMENTS)} replacements, parses clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
