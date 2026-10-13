"""GRD slice selection and assembly validation.

Sentinel-1 GRD products are cut into fixed along-track slices. On relative
orbit 1 the Oak Park AOI sits inside a single slice throughout 2021-2026 but
straddles a slice boundary from 2016 to mid-2020: the best single slice covers
0.8232 of the AOI, stable to four decimals, with the remaining 17.7% in the
neighbour. 122 of the 316 acquisitions on this orbit are affected, including
all 34 in 2018 -- the confirmatory year.

REQ-17 excluded those dates because mosaicking was not implemented. This module
replaces that exclusion with slice selection and pre-assembly validation. The
assembly itself is one SNAP `SliceAssembly` call; everything that can be got
wrong is in choosing what to feed it, which is what lives here.

Two hazards this module exists to catch
---------------------------------------
**Catalogue duplicates.** 83 dates carry the same real slice published more
than once -- identical datatake and start time to the microsecond, footprints
differing by about a metre, different product IDs. They are separate
processings of one slice. Feeding both to SliceAssembly would assemble a
product with a duplicated strip.

**Mixed processor baselines across a seam.** Thermal-noise vectors changed
between IPF baselines. A uniform offset cancels in a same-image spatial
contrast, but two slices on different baselines put a radiometric *step* at the
seam, and that does not cancel unless the strata are distributed evenly across
it. `ipf_consistent` is the gate; it needs the versions read from the
downloaded SAFEs, so it is called after download and before assembly.

Design note
-----------
Every function here is pure and takes plain data: rows as read from
`scenes.csv`, and a shapely geometry for the AOI. No HTTP, no filesystem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

# S1A_IW_GRDH_1SDV_20180704T181416_20180704T181441_022648_027435_4422.SAFE
NAME = re.compile(
    r"^(?P<platform>S1[ABCD])_IW_GRDH_1S(?P<pol>DV|SV)_"
    r"(?P<start>\d{8}T\d{6})_(?P<stop>\d{8}T\d{6})_"
    r"(?P<abs_orbit>[0-9A-F]{6})_(?P<datatake>[0-9A-F]{6})_"
    r"(?P<unique>[0-9A-F]{4})\.SAFE$")

TIME_FMT = "%Y%m%dT%H%M%S"

# Slice k's stop should equal slice k+1's start. Allow a little slack: the
# catalogue times are rounded to the second and adjacent slices overlap
# slightly by design.
CONTIGUITY_TOLERANCE_S = 3.0

# The union of selected slices must cover essentially all of the AOI. Short of
# this and assembly buys nothing -- the result is still a partial footprint,
# which is the failure REQ-17 was written to prevent.
MIN_UNION_COVERAGE = 0.999

# Degrees of slack when testing whether slices join.
#
# Adjacent IW GRD slices overlap in the imagery by design, but the catalogue
# publishes each footprint as a simplified quadrilateral, so the shared edge
# can disagree by a few metres: on 2018-07-04 the two slices describe the same
# boundary as (-8.689227, 52.554928)-(-4.957621, 52.954735) and
# (-8.689258, 52.555000)-(-4.956024, 52.954971), about 3 m apart. Unioned raw,
# that hairline makes a MultiPolygon and every real pair looks disjoint.
#
# 0.005 degrees is roughly 550 m: ample to close a metres-wide sliver, and
# nowhere near enough to bridge a genuinely missing slice, which would leave a
# gap of order 170 km along-track.
JOIN_TOLERANCE_DEG = 0.005


@dataclass(frozen=True)
class SliceKey:
    """Identifies one *real* slice, independent of how often it was published."""
    datatake: str
    start: str      # second resolution; microsecond differences are not slices


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def parse_name(name: str) -> dict | None:
    """Pull the fields out of a GRD product name, or None if it doesn't match.

    Returning None rather than raising lets a caller skip an odd product and
    report it, instead of aborting a 316-acquisition plan over one name.
    """
    m = NAME.match(name)
    if not m:
        return None
    d = m.groupdict()
    d["start_dt"] = datetime.strptime(d["start"], TIME_FMT)
    d["stop_dt"] = datetime.strptime(d["stop"], TIME_FMT)
    return d


def slice_key(name: str) -> SliceKey | None:
    """The identity of the real slice a product is a copy of."""
    p = parse_name(name)
    if p is None:
        return None
    return SliceKey(datatake=p["datatake"], start=p["start"])


# --------------------------------------------------------------------------
# de-duplication
# --------------------------------------------------------------------------

def dedupe(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """One product per real slice. Returns (kept, dropped).

    Where a slice was published more than once, the product with the
    lexicographically largest name is kept. That choice is arbitrary -- nothing
    in the catalogue listing orders the processings -- but it is deterministic,
    so a rerun selects the same products, and every dropped product is returned
    for the audit record rather than silently discarded.

    The radiometric question the choice raises is not settled here: see
    `ipf_consistent`, which compares the baselines actually downloaded.
    """
    best: dict[SliceKey, dict] = {}
    unparsed: list[dict] = []
    for r in rows:
        key = slice_key(r["name"])
        if key is None:
            unparsed.append(r)
            continue
        prev = best.get(key)
        if prev is None or r["name"] > prev["name"]:
            best[key] = r

    kept_names = {r["name"] for r in best.values()}
    kept = [r for r in rows if r["name"] in kept_names]
    dropped = [r for r in rows
               if r["name"] not in kept_names and r not in unparsed]
    return kept, dropped + unparsed


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

def footprint(row: dict) -> BaseGeometry | None:
    text = (row.get("footprint_wkt") or "").strip()
    if not text:
        return None
    try:
        return shapely_wkt.loads(text)
    except Exception:
        return None


def intersecting(rows: list[dict], aoi: BaseGeometry) -> list[dict]:
    """Only the slices that actually touch the AOI.

    A pass over Ireland can arrive as four slices while two of them are
    hundreds of kilometres from Carlow. Downloading those would be 3.4 GB each
    for nothing, and feeding them to SliceAssembly would widen the assembled
    product for no gain.
    """
    out = []
    for r in rows:
        fp = footprint(r)
        if fp is not None and fp.intersects(aoi) and not fp.touches(aoi):
            out.append(r)
    return out


def single_coverage(row: dict, aoi: BaseGeometry) -> float:
    """Fraction of the AOI inside one product's footprint.

    Mirrors the `aoi_coverage` column `s1_recon` writes, recomputed here so
    planning does not depend on a value carried through a CSV round-trip.
    """
    fp = footprint(row)
    if fp is None or aoi.area == 0:
        return 0.0
    return fp.intersection(aoi).area / aoi.area


def assembly_order(rows: list[dict]) -> list[dict]:
    """Time order. SliceAssembly expects consecutive slices along-track."""
    def key(r):
        p = parse_name(r["name"])
        return p["start_dt"] if p else datetime.max
    return sorted(rows, key=key)


def union_coverage(rows: list[dict], aoi: BaseGeometry) -> tuple[float, int]:
    """(fraction of the AOI covered by the union, number of disjoint parts).

    Mirrors `s1_recon.coverage_stats`, which judges a date on the union of its
    slices rather than on any single product.

    Coverage is measured on the footprints as published -- buffering them would
    inflate it at the AOI edge. The part count is measured on footprints
    buffered by JOIN_TOLERANCE_DEG, so a metres-wide sliver between abutting
    slices does not read as a gap. See that constant for why the two differ.
    """
    parts = [fp for fp in (footprint(r) for r in rows) if fp is not None]
    if not parts:
        return 0.0, 0

    merged = unary_union(parts)
    joined = unary_union([fp.buffer(JOIN_TOLERANCE_DEG) for fp in parts])
    n_parts = len(joined.geoms) if hasattr(joined, "geoms") else 1

    if aoi.area == 0:
        return 0.0, n_parts
    return merged.intersection(aoi).area / aoi.area, n_parts


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def assembly_problems(rows: list[dict], aoi: BaseGeometry) -> list[str]:
    """Reasons this set of slices must not be assembled. Empty means proceed.

    Each check guards a failure that would otherwise be invisible in the
    output: a product with a hole in it, a strip counted twice, or two
    unrelated passes welded together.
    """
    problems: list[str] = []
    if not rows:
        return ["no products"]

    parsed = [(r, parse_name(r["name"])) for r in rows]
    unparsed = [r["name"] for r, p in parsed if p is None]
    if unparsed:
        problems.append(f"unparsed product name(s): {', '.join(sorted(unparsed))}")
        return problems

    good = [(r, p) for r, p in parsed]

    platforms = {p["platform"] for _, p in good}
    if len(platforms) > 1:
        problems.append(f"mixed platforms: {', '.join(sorted(platforms))}")

    datatakes = {p["datatake"] for _, p in good}
    if len(datatakes) > 1:
        problems.append(f"slices from different datatakes: "
                        f"{', '.join(sorted(datatakes))}")

    keys = [slice_key(r["name"]) for r, _ in good]
    if len(set(keys)) != len(keys):
        problems.append("duplicate slices present; run dedupe() first")

    ordered = assembly_order([r for r, _ in good])
    pairs = [parse_name(r["name"]) for r in ordered]
    for a, b in zip(pairs, pairs[1:]):
        gap = (b["start_dt"] - a["stop_dt"]).total_seconds()
        if abs(gap) > CONTIGUITY_TOLERANCE_S:
            problems.append(
                f"non-contiguous slices: {a['start']} ends {a['stop']}, "
                f"next starts {b['start']} ({gap:+.0f} s)")

    cov, n_parts = union_coverage([r for r, _ in good], aoi)
    if n_parts > 1:
        problems.append(f"slice footprints do not join ({n_parts} parts)")
    if cov < MIN_UNION_COVERAGE:
        problems.append(f"union covers {cov:.4f} of the AOI, "
                        f"below {MIN_UNION_COVERAGE}")

    return problems


def ipf_consistent(versions: dict[str, str]) -> list[str]:
    """Check the slices about to be assembled share one processor baseline.

    `versions` maps product name to IPF version as read from each downloaded
    SAFE's manifest. Called after download, before assembly.

    A uniform radiometric offset between baselines cancels in a same-image
    spatial contrast, which is why inter-platform calibration does not matter
    to the grassland-minus-forest result. A step *across the seam* is a
    different thing: it only cancels if every stratum is distributed evenly on
    both sides of the boundary, and nothing guarantees that.
    """
    present = {k: v for k, v in versions.items() if v}
    missing = sorted(k for k, v in versions.items() if not v)
    problems = []
    if missing:
        problems.append(f"IPF version unreadable for: {', '.join(missing)}")
    distinct = set(present.values())
    if len(distinct) > 1:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(present.items()))
        problems.append(f"slices on different IPF baselines ({detail}); "
                        f"assembling them puts a radiometric step at the seam")
    return problems


# --------------------------------------------------------------------------
# the planning entry point
# --------------------------------------------------------------------------

def plan_acquisition(rows: list[dict], aoi: BaseGeometry) -> dict:
    """Decide what to do with one date's products.

    Returns a dict with:
      action   'single' | 'assemble' | 'exclude'
      products ordered rows to download and feed to gpt
      dropped  duplicate products not used
      reason   why, when excluded
    """
    kept, dropped = dedupe(rows)
    touching = intersecting(kept, aoi)

    if not touching:
        return {"action": "exclude", "products": [], "dropped": dropped,
                "reason": "no slice intersects the AOI"}

    # Prefer a single slice wherever one already covers the AOI on its own.
    #
    # This is not only cheaper (one 1.7 GB product instead of two and no
    # assembly step) -- it is what 2022-10-11 needs. That date carries two
    # products from one datatake, re-sliced two seconds apart, each covering
    # the AOI at 1.0000. Assembling them would weld together two near-identical
    # overlapping strips; excluding the date would discard a perfectly good
    # acquisition. Taking one is the only sensible answer, and keeping assembly
    # for the dates that genuinely need it keeps the processing path for
    # 2021-2026 identical to the one that produced the existing results.
    full = [(c, r) for r, c in ((r, single_coverage(r, aoi)) for r in touching)
            if c >= MIN_UNION_COVERAGE]
    if full:
        # Coverage is rounded before comparing so the choice does not turn on a
        # difference in the tenth decimal place. On 2022-10-11 both products
        # cover the AOI and their footprints differ by about a metre; rounding
        # sends that to the name, which is stable, rather than to a floating
        # point comparison of two areas that are the same to any meaning.
        best = max(full, key=lambda cr: (round(cr[0], 6), cr[1]["name"]))[1]
        return {"action": "single", "products": [best],
                "dropped": dropped + [r for r in touching if r is not best],
                "reason": ""}

    if len(touching) == 1:
        cov = single_coverage(touching[0], aoi)
        return {"action": "exclude", "products": [], "dropped": dropped,
                "reason": f"single slice covers only {cov:.4f} of the AOI "
                          f"and no neighbour is in the catalogue"}

    problems = assembly_problems(touching, aoi)
    if problems:
        return {"action": "exclude", "products": [], "dropped": dropped,
                "reason": "; ".join(problems)}

    return {"action": "assemble", "products": assembly_order(touching),
            "dropped": dropped, "reason": ""}
