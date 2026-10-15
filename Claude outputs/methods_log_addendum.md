
---

## 13 October 2026 — NCR-17: REQ-17 removed the confirmatory year

The eighth re-specification, and the first forced by the data configuration
rather than the method.

### How it surfaced

T1's pre-flight dry run, before any download. REQ-17 excluded **120 of 157**
acquisitions in 2016–2020, including every 2018 date from 11 April to
26 October at unbroken 6-day spacing. 2019 and 2020 likewise. The 37 survivors
were scraps in 2016–17. The confirmatory test had no treatment year.

REQ-17 excluded any date arriving as more than one GRD slice, because
mosaicking was not implemented and half-processing an acquisition would have
put a partial footprint into the series with nothing downstream to catch it.
That was the right call when written. It had been invisible for six years
because on relative orbit 1 the AOI happens to sit inside a single slice
throughout 2021–2026.

### What the data said

- **Best single slice covers 0.8232 of the AOI**, stable to four decimals
  across every 2018 date. A fixed slicing grid, not a drifting one, so slice
  selection could not fix it. 17.7% sits in the neighbouring slice.
- **No alternative orbit exists.** `orbits.csv` across 2016–2026 holds three
  ASCENDING candidates: orbit 1 at min coverage 1.000 (VIABLE, 122 sliced),
  orbit 74 at 0.323 and orbit 103 at 0.178, both "partial coverage". The
  alternatives are not near-misses, they are the wrong swath.
- **The slices are one pass, not two.** Same platform, same absolute orbit
  022648, same datatake 027435, and slice 1 stops at 18:14:41 as slice 2
  starts. The cut is an ESA packaging decision applied on the ground to a
  continuous recording, which is why rejoining it is lossless. Had it been a
  genuine break in acquisition, 2018 would have been unrecoverable.

### Three things found only by running against the real catalogue

Each would have passed a fixture-based test, because the fixtures would have
encoded the same assumption as the code.

1. **The "4 slices" dates are two slices published twice.** 83 dates carry
   duplicate products — identical datatake and start time to the microsecond,
   footprints about a metre apart, different trailing product IDs. 166 products
   in total. Feeding both to SliceAssembly would have assembled a strip with
   itself.
2. **The first contiguity test rejected all 121 genuine pairs.** The catalogue
   describes the shared edge between abutting slices about 3 m apart, so a raw
   union is a MultiPolygon and every real pair reads as disjoint. The imagery
   overlaps by design; the simplified quadrilaterals do not.
   `JOIN_TOLERANCE_DEG` is 550 m — enough for a metres-wide sliver, nowhere
   near enough to bridge a missing slice, which would leave ~170 km.
3. **2022-10-11 needs neither assembly nor exclusion.** Two products from one
   datatake, re-sliced two seconds apart, each covering the AOI at 1.0000. That
   produced a better general rule: prefer a single slice wherever one covers
   the AOI alone, assemble only where none does. It also recovers both former
   REQ-17 exclusions, taking the existing record from 156 to **158**.

Result across all 316 acquisitions on orbit 1: **195 single, 121 assembled,
0 excluded.**

### The design error, and SNAP catching it

The first implementation assembled the raw products with a separate
`gpt SliceAssembly` call, then ran the existing chain on the result. The
reasoning was to keep graph v3 byte-identical so that "the processing chain did
not change" stayed a fact about the files rather than an argument.

SNAP refused it:

```
OperatorException: Noise removal should be applied prior to slice assembly
```

Thermal-noise lookup tables are per-slice and indexed by azimuth line. Applied
to a product already two slices long the indices are meaningless, so SNAP
raises rather than subtracting the wrong vectors. **This is the hazard the
acceptance test existed to detect, and the operator detected it first.** The
error would have landed on VH over dry bare soil — where backscatter approaches
the noise floor, and where this study takes its measurement.

Graph v4 therefore carries two branches: read, orbit, noise removal per slice,
joined by SliceAssembly, with everything downstream running once on the
assembled product. Border-noise removal stays *after* assembly deliberately —
run per slice it would trim the along-track edges that become the interior
seam, cutting a gap into the middle of the product.

v4 was generated from v3 programmatically rather than written by hand, so the
shared operators are byte-identical as a matter of record. Node-by-node:
branch 1 and everything from Calibration onward identical to v3; branch 2 an
exact copy of branch 1 reading `${input2}`; `Remove-GRD-Border-Noise` identical
apart from its single changed source. One further error was found in the first
generated v4 — the SliceAssembly node had an `id`, sources and parameters but
no `<operator>` element, so SNAP failed on a null operator name. The file was
well-formed XML, which is why a parse check did not catch it; the generator now
asserts every node carries a non-empty operator.

### Acceptance test — 2018-07-04

Assembled scene versus each slice processed alone through v3, compared over
that slice's own ground. SNAP's post-terrain-correction no-data is 0.0, so
joint-validity masking restricts each comparison to its slice's footprint
without any seam geometry being specified.

| comparison | σ⁰ VV | σ⁰ VH | cross-ratio | pixels |
|:--|---:|---:|---:|---:|
| assembled vs north slice (0.8232) | +0.0000 dB | −0.0000 dB | −0.0001 dB | 12,482,448 |
| assembled vs south slice (0.1766) | −0.0011 dB | −0.0011 dB | +0.0000 dB | 3,506,460 |

Threshold 0.171 dB, from REQ-09's worst-channel inter-platform agreement. All
three products on `('EPSG:2157', 10.0, 10.0, 5.0, 5.0)`; sub-pixel misalignment
0.000 px. Both slices on IPF 002.91, so the pre-assembly processor-baseline
gate passed on its first real use.

The agreement is this good because each slice is noise-corrected independently
before being joined, so over each slice's own ground the assembled scene is the
same arithmetic, not an approximation of it.

Two observations worth keeping. The southern residual of −0.0011 dB is
**identical in VV and VH**, so the cross-ratio comes out at +0.0000 — a direct
measurement of the common-mode cancellation that the whole contrast argument
rests on. And the residual appears only on the southern slice; the most likely
cause is border-noise removal trimming that slice's northern edge when
processed alone, where the same edge is interior in the assembly. That was not
tested, and at 0.0011 dB it does not warrant testing.

### Consequences

- REQ-17 is retired and replaced by a slice-assembly requirement.
- `slices.py` (58 tests) holds the planning logic; `check_assembly.py` is the
  acceptance test; `ipf_check.py` (38 tests) audits processor baselines.
- The existing record recovers from 156 to 158 acquisitions.
- 2018 is 34 assembled acquisitions out of 35 — more heavily assembled than any
  baseline year except 2019 and 2020. Recorded as a known asymmetry in
  Amendment 1 to the pre-registration.
