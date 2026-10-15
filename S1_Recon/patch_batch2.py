"""Move slice assembly inside the SNAP graph.

Applies on top of patch_batch.py. The first design assembled the raw products
with a separate `gpt SliceAssembly` call and then ran the chain on the result.
SNAP refuses that:

    OperatorException: Noise removal should be applied prior to slice assembly

Thermal-noise lookup tables are per-slice and indexed by azimuth line, so they
cannot be applied to a product that is already two slices long. Graph v4 now
carries two branches -- read, orbit, noise removal per slice -- joined by
SliceAssembly, with everything downstream running once on the assembled
product. There is no intermediate file and no second gpt invocation, so this
patch removes more than it adds.

Usage:
    python patch_batch2.py <path to batch_process.py>
"""

from __future__ import annotations

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# P1  run_gpt passes one -Pinput per slice
# --------------------------------------------------------------------------

P1_OLD = '''def run_gpt(gpt: Path, graph: Path, src: Path, dst: Path,
            cache: str, threads: int, log: Path) -> tuple[bool, str]:
    cmd = [str(gpt), str(graph), f"-Pinput={src}", f"-Poutput={dst}",
           "-c", cache, "-q", str(threads)]
'''

P1_NEW = '''def run_gpt(gpt: Path, graph: Path, srcs, dst: Path,
            cache: str, threads: int, log: Path) -> tuple[bool, str]:
    """Run a graph over one or more source products.

    v3 takes a single product as ${input}. v4 assembles two slices and takes
    them as ${input} and ${input2}, in acquisition order -- SliceAssembly
    concatenates along-track, so the order is not decorative.
    """
    if isinstance(srcs, Path):
        srcs = [srcs]
    inputs = [f"-Pinput={srcs[0]}"]
    inputs += [f"-Pinput{i}={s}" for i, s in enumerate(srcs[1:], start=2)]
    cmd = [str(gpt), str(graph), *inputs, f"-Poutput={dst}",
           "-c", cache, "-q", str(threads)]
'''

# --------------------------------------------------------------------------
# P2  the separate assembly call and its intermediate are gone
# --------------------------------------------------------------------------

P2_OLD = '''def run_assembly(gpt: Path, srcs: Sequence[Path], dst: Path,
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

P2_NEW = '''def verify(dim: Path, aoi: Path, log: Path) -> tuple[bool, str]:
'''

# --------------------------------------------------------------------------
# P3  the processing step: one graph call, no intermediate
# --------------------------------------------------------------------------

P3_OLD = '''            dim = args.out / f"{job.stem}.dim"
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
'''

P3_NEW = '''            dim = args.out / f"{job.stem}.dim"
            logs = args.out / "logs"
            t0 = time.time()
            graph = args.graph
            versions: dict[str, str] = {}

            if job.action == "assemble":
                # The seam check, before the slices are joined. A uniform
                # offset between IPF baselines cancels in a same-image spatial
                # contrast; a step across the seam only cancels if every
                # stratum is spread evenly on both sides of it, and nothing
                # guarantees that.
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
                graph = args.graph_assembled

            # v4 assembles inside the graph, so both slices go to one gpt call
            # and there is no intermediate product to clean up. SNAP will not
            # remove thermal noise from an already-assembled product, which is
            # why assembly cannot be a separate earlier step.
            ok, detail = run_gpt(args.gpt, graph, src, dim, args.cache,
                                 args.threads, logs / f"{job.stem}.gpt.log")
            proc_s = time.time() - t0
'''

REPLACEMENTS = [
    ("P1 run_gpt multi-input", P1_OLD, P1_NEW),
    ("P2 drop the separate assembly call", P2_OLD, P2_NEW),
    ("P3 processing step", P3_OLD, P3_NEW),
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
        print("\\nThis patch applies on top of patch_batch.py. Run that first.",
              file=sys.stderr)
        return 1

    for leftover in ("run_assembly", "discard_assembly"):
        if leftover in text:
            print(f"PATCH NOT APPLIED — {leftover} still referenced",
                  file=sys.stderr)
            return 1

    import ast
    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"PATCH NOT APPLIED — result would not parse: {exc}",
              file=sys.stderr)
        return 1

    backup = path.with_suffix(".py.pre-ingraph")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"backup: {backup.name}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name}: {len(REPLACEMENTS)} replacements, parses clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
