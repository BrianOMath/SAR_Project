# Remaining work — SAR drought 2026

Brian Ó Mathúna · 12 October 2026

**Where the project stands:** the pipeline is built, validated and documented.
156 acquisitions processed across six years with zero failures. One result
below p = 0.05, not yet confirmed. Everything below exists to settle that
result and finish the write-up.

Tasks are ordered by dependency, not by size. **T1 determines the headline of
the technical report**, so the report cannot be finalised before it.

---

## T1 — The confirmatory run (2016–2020)

**The decisive task. Everything else is bookkeeping by comparison.**

### Why

2026's result rests on one test at p = 0.0398 among thirty-six, which fails
multiplicity correction and fails its own pre-specified coherence criterion on
tillage. It needs testing on data that did not generate it.

**2018 is a near-perfect out-of-sample test.** From the Oak Park record:

| year | peak SMD | days > 70 mm | deficit-days |
|---:|---:|---:|---:|
| **2018** | 96.8 mm | 51 | **2,308** |
| **2026** | 96.2 mm | 46 | **1,915** |
| 2020 | 80.0 | 21 | 950 |
| 2013 | 82.8 | 18 | 670 |
| 2022 | 73.6 | 3 | 644 |

2018 is the **most severe drought in the 23-year record**, marginally ahead of
2026, with a nearly identical peak. Sentinel-1A and 1B were both flying, so
orbit 1 had the same 6-day cadence as 2021 and 2026.

Everything needed is already frozen: the hypothesis (grassland − forest
cross-ratio senescence slope), the window rule (longest spell SMD ≥ 50 mm,
≥ 10 days), the processing chain, the strata, the erosion. **The SAR for those
years has never been looked at.**

### Scope

Process **2016–2020**. That yields 2018 as a second treatment year, 2016/2017/
2019 as additional baselines, 2020 as a possible third treatment point
(moderately severe at 950 deficit-days), and an eleven-year record that also
strengthens the 2026 test.

| | full scope (2016–2020) | minimum viable (2017–2019) |
|:--|:--|:--|
| acquisitions | ~160 | ~105 |
| download | ~140 GB | ~90 GB |
| output | ~85 GB | ~56 GB |
| wall clock | ~10 h | ~7 h |
| gives | 2 treatment years, 3 new baselines | 2018 + 2 near-neighbour baselines |

**Disk check first.** Current `C:\sar\proc` is ~84 GB. Full scope takes it to
roughly **170 GB**. Move `--out` to the Samsung SSD if needed — keep `--raw` on
the same volume, since `MIN_FREE_GB` only watches the raw folder.

### Steps

1. Re-run the recon for 2016–2026 in one pass, so `scenes.csv` covers the whole
   record. Check coverage holds and note any year whose max limb gap exceeds
   ~18 days.
2. Verify the **Sentinel-1 processor baseline (IPF version)** for 2016–2018
   products. Thermal-noise vectors improved with later baselines, and a
   baseline change inside the series would mimic a trend. It cancels in the
   contrasts — same argument as platform calibration — but affects the absolute
   series and must be stated.
3. Batch with graph v3. Already-verified scenes skip automatically.
4. `build_series.py`, then `fetch_met.py --year 2018` to derive 2018's window
   **by the same rule**, frozen to its own JSON before any SAR test.
5. `stratify.py` with `--treat-year 2018`, `--base-years` set to the non-drought
   years, and `--window-from` the 2018 JSON. All three observables.

### Reading the outcome

- **2018 shows the same doubling** → two independent severe droughts, same
  signature, pre-specified test. The result stands and the report's headline
  changes.
- **2018 shows nothing** → 2026 was most likely one of the 1.8 expected false
  positives. The sensitivity conclusion stands as written and is strengthened
  by having been tested properly.
- **Either outcome is publishable.** Decide in advance that both will be
  reported, so the decision is not made after seeing which one arrived.

---

## T2 — Plan to rev. 5

Small, and blocking nothing, but it is the audit record.

- Log **NCR-14** (slope test mis-specified for non-linear observables),
  **NCR-15** (`--local` PermissionError misdirection), **NCR-16** ("days above
  threshold" counted only days inside qualifying spells).
- Rewrite the §15 process note around the sixteen-NCR classification: fifteen
  plumbing, one method; seven of them a correct computation with the wrong
  words on top; three of those diagnostics that misdirected the operator.
- Record the final data configuration: 158 acquisitions on orbit 1, 156
  processed, 2 REQ-17 exclusions, 157/158 at 1.0000 coverage.
- Add the REQ-09 result (0.171 dB worst channel, 0.011 dB cross-ratio) and the
  τ = 0.000 repeatability finding.
- Update **REQ-14** to the CSO target (~1 May 2027).
- Add a requirement covering the frozen-window discipline: any test window must
  be derived from data independent of the SAR and written with its rule and
  timestamp before the test runs.

---

## T3 — Technical report to rev. 2

**Blocked by T1.** The headline depends on the 2018 outcome.

- Add the window-restricted result with its full caveat set.
- Add NCR-14 and the level test; mark the VV/VH slope tables **superseded**
  rather than deleting them — they are the evidence for NCR-14.
- Add §6.2's second worked example of the single-baseline trap (VH tillage,
  p = 0.046 → 0.20).
- Correct §6.1: the claim that the cross-ratio might be hiding a common-mode
  signal was tested and refuted. State the τ comparison (0.035 vs 0.496 dB) as
  the evidence-backed reason to prefer it.
- Resolve the open limitation: the level difference-in-differences still
  compares against 2025 alone and its p = 0.0087 should be withdrawn or
  recomputed against the baseline distribution.
- Add the SMD severity table and the independent-corroboration finding (SMD
  break 29 Aug, SAR recovery 28 Aug – 3 Sep).

---

## T4 — Figures

**Partly blocked by T1.** Build what is stable now, redo after.

- Re-run `figures.py` on the window-restricted series to produce a second set.
- Add a fifth figure: **SMD and the SAR contrast on a shared time axis** for
  2026, with the frozen window shaded. It carries the corroboration finding
  better than any table, and it is the figure a reviewer will look at first.
- Consider a sixth once T1 lands: 2018 and 2026 side by side, same axes.

---

## T5 — Repository hygiene

Cheap, and currently the weakest part of an otherwise careful project.

- Commit `results/phase2/`, `phase3/`, `phase4/` including
  `drought_window.json` — the frozen window is a provenance artefact and must
  be in version history.
- Commit `data/landcover/nlcm_2018_aoi.geojson` and `data/met/`.
- Confirm `recon_out/scenes.csv` and `orbits.csv` are tracked (the `.gitignore`
  negation was added; verify it took).
- Write the root **README**: what the repo is, the five scripts in order, how
  to reproduce from a clean clone, where the plan / report / methods log live.
- Add `matplotlib` and `scipy` to CI if the workflow pins its own list.

---

## T6 — The pre-registered prediction (REQ-14)

**Dormant until ~1 May 2027.**

Before that date, write down the predicted direction and magnitude for the CSO
*Area, Yield and Production of Crops* release for the 2026 crop year, with the
reasoning, committed to the repo and timestamped. Describe it as predicting an
unpublished measurement, never as predicting a future event.

---

## Optional extensions, in order of value

Only worth starting once T1–T5 are done.

1. **SMD as a regressor.** Instead of a binary window, regress the contrast on
   soil moisture deficit directly. Converts a correlational result into a
   dose–response one and uses the whole series rather than a subset.
2. **Drainage-stratified grassland control.** The precision table showed
   dry − wet grassland beat grassland − forest by 2× on 2% of the pixels. A
   control matched on crop and management, differing only in water-holding
   capacity, should beat both.
3. **Sentinel-2 NDVI over identical strata.** A cross-sensor comparison. If
   optical resolves what SAR cannot, the detection-limit result gains a
   reference point and the report gains a much stronger conclusion.
4. **A second AOI.** Independent pixels, same frozen hypothesis. Weaker than
   T1 because Irish droughts are spatially correlated, so it is less
   independent than a different year.

---

## Explicitly not worth doing

**More baseline years for the 2026 full-limb test.** The variance decomposition
settles it: 82% of the uncertainty is 2026's own fit error and 0% is
between-year variation, so the detection threshold falls only from 0.147 to
0.107 dB/month going from five baseline years to fifteen. T1 adds years for a
different reason — a second treatment year — not to sharpen 2026.

**Re-processing at finer resolution or a different projection.** The pipeline is
validated at τ = 0.000 across five years and four platforms. Nothing in the
null points at the processing.

**Narrowing the window further.** The current window came from an independent
rule specified in advance. Any further narrowing would have to come from
another independent rule, specified before looking — and there is no obvious
candidate.
