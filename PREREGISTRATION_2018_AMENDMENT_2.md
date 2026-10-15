# Amendment 2 to the 2018 pre-registration

**Recorded observation. No change to the hypothesis, the test, the baseline
set or the decision thresholds.**

Brian Ó Mathúna · 15 October 2026

---

## Status when this was written

`PREREGISTRATION_2018.md` (12 October) and Amendment 1 (13 October) are
committed and pushed. Since then:

- **The 2016–2020 batch completed.** 157 acquisitions, zero failures
  outstanding. 121 of the 316 on relative orbit 1 are assembled from two GRD
  slices; 2018 is 34 of 35.
- **`build_series.py` ran across the whole archive.** All 316 scenes share one
  pixel lattice, `('EPSG:2157', 10.0, 10.0, 5.0, 5.0)`, and every acquisition
  reports 100% valid pixels. This is the slice-assembly acceptance test at full
  scale.
- **`ipf_check.py` ran across the whole archive**, recording the processor
  baseline of all 316 scenes.

**No stratified series, contrast, slope or level has been computed for any
year.** `stratify.py` has not been run since the archive was extended.

---

## What was observed

### Processor baselines across the record

21 distinct IPF versions, 002.62 through 004.03 — a decade of ground-segment
software in one archive. Restricted to the **fit range fixed by Amendment 1,
DOY 182–253**:

| year | role | versions in the fit range | n |
|:--|:--|:--|---:|
| 2016 | baseline | **2.71, 2.72** | 6 |
| 2017 | baseline | **2.82, 2.84** | 12 |
| 2018 | treatment | 2.91 | 12 |
| 2019 | baseline | 3.10 | 12 |
| 2020 | baseline | 3.31 | 12 |
| 2021 | baseline | 3.31 | 12 |
| 2022 | baseline | 3.52 | 6 |
| 2023 | baseline | 3.61 | 6 |
| 2024 | baseline | 3.80 | 5 |
| 2025 | baseline | 3.92 | 12 |
| 2026 | treatment | 4.03 | 12 |

**Both treatment years are on a single baseline through the limb**, as are
seven of the nine baseline years. Three change version within days of the fit
range opening and fall outside it: 2018 at DOY 179, 2019 at DOY 180, 2020 at
DOY 175. That is coincidence, not design — ESA ships in late June and the limb
starts on 1 July.

Only **2016** (2.71 → 2.72 at DOY 244) and **2017** (2.82 → 2.84 at DOY 238)
carry a version change inside the fit range.

### An offset visible in the whole-AOI aggregate

`build_series.py` prints a July–August mean cross-ratio per year as a smoke
test. 2016 and 2017 sit near −5.92 and −6.05 dB against roughly −6.50 dB for
every other year: an offset of about half a decibel, in the two years on the
oldest calibration tables.

---

## The decision, and why

**2016 and 2017 are retained. No year is dropped.**

**A within-year version change is the case the contrast does not protect
against.** A uniform offset between processor baselines cancels when forest is
subtracted from grassland in the same image. A step *inside* a year does not
cancel in that year's slope fit: it has the same shape as a change in
vegetation. This is why the check was specified.

**Neither change crosses a baseline where thermal-noise handling was reworked.**
002.90 and 003.10 are the two releases that matter most for noise vectors, and
2.71 → 2.72 and 2.82 → 2.84 are increments within a generation, not across one.

**This last point is a judgement, not a measurement**, and is recorded as such.
The epoch list encodes which releases changed noise handling materially; it is
not derived from this project's data. If a reader disagrees with it, the
consequence is stated below.

**Every year clears the acquisition-count floor.** The pre-registration drops a
year holding fewer than four acquisitions in the window. The minimum is 2024
with five.

---

## What was looked at, and what it did not affect

The per-year aggregate above includes 2018 and 2026. It was printed
automatically by `build_series.py` and could not be avoided once that script
ran.

It is recorded here that it was seen, and that **nothing in the specification
changed after seeing it.** The hypothesis, contrast, window, fit range,
baseline membership, decision thresholds and co-primary tests are exactly as
fixed on 12 and 13 October. This amendment adds an observation and a
limitation; it removes no year, changes no threshold and alters no test.

The aggregate is in any case the whole-AOI mean across grassland, tillage,
forest, bog and town — the quantity the stratification exists to replace. It
cannot stand in for the test, and is not being used as a preview of it.

---

## Reported as a limitation either way

Whatever the outcome, the report states that two of nine baseline years carry a
minor processor-baseline change inside the senescence limb, and that the two
oldest-baseline years show an absolute offset of roughly 0.5 dB in the
whole-AOI aggregate.

The offset is also a worked demonstration of why the design uses a contrast:
half a decibel applied uniformly to an image would be a serious problem for an
absolute comparison across years, and vanishes on subtracting two strata
measured in the same image.

**What would change this decision.** If the leave-one-out calibration reported
by `stratify.py` places 2016 or 2017 outside its own prediction interval while
the other baseline years sit inside, that is evidence the processor change
matters at the scale of this measurement. In that event both years are dropped,
the test is re-run on seven baselines (df = 6, t = 2.447), and **both results
are reported** — the nine-year version as pre-specified and the seven-year
version as a sensitivity analysis, with this paragraph as the reason.
