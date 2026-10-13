# Amendment 1 to the 2018 pre-registration

**Made before any 2018 Sentinel-1 product had been processed.**

Brian Ó Mathúna · 13 October 2026

---

## Status when this was written

`PREREGISTRATION_2018.md` was committed and pushed on 12 October. Since then:

- The 2018 drought window was derived from Met Éireann data and frozen:
  **DOY 151–253** (31 May – 10 Sep), 103 days, peak SMD 96.8 mm on 19 July.
- The confirmatory run was prepared and **aborted at pre-flight**: REQ-17
  excluded every 2018 acquisition on relative orbit 1, because the AOI
  straddles a GRD slice boundary in that era. Slice assembly has since been
  implemented and validated (NCR-17).
- **One 2018 acquisition has been processed** — 2018-07-04, as the assembly
  acceptance test. Its σ⁰ was compared against the same date's individual
  slices and nothing else. No stratification, no contrast, no time series, no
  test of any kind has been run on 2018 data.

Everything below is therefore still decided blind. The window is unchanged and
remains as frozen.

---

## Why an amendment is needed

The original pre-registration named the **senescence slope within the
met-derived window** as the primary test. That was written before the 2018
window existed. The window came back as DOY 151–253, and `PEAK_DOY` in
`stratify.py` is 182.

A fit over DOY 151–253 therefore spans roughly thirty days of biomass
*accumulation* before the turning point, then the senescence limb. A straight
line through a maximum is not a senescence rate. It would also fit badly: mean
r² for the cross-ratio over the proper limb is already only 0.51, and through a
turning point it is worse, which inflates the standard errors and spends the
power the nine-year baseline was meant to buy.

This is a definitional error in the original, visible from the met data alone
and with no SAR involved.

---

## The three changes

### 1. The fit is restricted to the senescence limb

The window still comes from the met rule, unchanged and already frozen. The
**fit range** is the window intersected with peak biomass: **DOY ≥ 182**. For
2018 that gives DOY 182–253.

As before, the same DOY range is applied to every baseline year, so all ten
years in the test are fitted over identical days and there is no between-year
window artefact inside the test.

### 2. The ratio prediction is withdrawn

The original predicted **slope₂₀₁₈ / baseline ≥ 1.5**, point estimate 2.1, from
2026's observed 2.07.

That comparison is not available. 2018's fit range is 72 days and 2026's was
58, and NCR-14 measured that window length alone moves slopes by sd 0.323
dB/month against a between-year spread of 0.256 — the artefact exceeds the
measurement. A slope over 72 days and a slope over 58 days are not the same
quantity, and their ratio to their own baselines cannot be compared without
assuming the limb is linear, which NCR-14 established it is not.

**The direction-plus-significance criterion is unchanged and remains primary:**
2018 steeper than baseline, and z ≤ −2.306 at df = 8.

What is given up is the effect-size prediction. That is a real loss of
stringency and is recorded as such.

### 3. The level test at DOY 227 becomes co-primary

`level_at_ref()` at day 227 is reported alongside the slope, with the same
decision thresholds.

Day 227 lies inside both the 2018 window (151–253) and the 2026 window
(183–240), so it is the one quantity directly comparable between the two
droughts. `stratify.py`'s own comment records that the level test is robust to
how each year's limb was sampled, unlike the slope — which is precisely the
property NCR-14 was raised about.

Both results are reported whichever way they fall. If slope and level
disagree, that disagreement is the finding and is reported as one, not
resolved by preferring whichever is more favourable.

---

## The baseline set, and running the test once

Confirmed unchanged: **2016, 2017, 2019, 2020, 2021, 2022, 2023, 2024, 2025** —
nine years, df = 8, two-sided 5% critical value t = 2.306. 2018 and 2026 are
the two drought years by the 90th-percentile rule on the Oak Park record.

All five of 2016–2020 will be processed **before the primary test is run**.
This is stated because the alternative was available and was declined: running
2018 against the existing five baselines now, then re-running against nine
later, would be two attempts at one hypothesis. The primary test runs once,
against the nine-year set.

If a year cannot be processed, or holds fewer than four acquisitions inside
DOY 182–253, it is dropped and the omission recorded before the test runs.

---

## Unchanged from the original

The hypothesis; the window rule and the frozen 2018 window; the drought-year
definition; grassland − forest cross-ratio as the confirmatory contrast; the
exclusion of tillage from the confirmatory criterion and the reason for it;
dry − wet grassland and σ⁰ VV/VH as secondary; the commitment to report either
outcome with equal prominence; and the recorded threats — processor baseline,
S1B calibration, uneven baseline sampling.

NCR-17 adds one threat to that list: **121 of 316 acquisitions are assembled
from two slices, and 2018 is 34 of 34.** The assembly acceptance test measured
agreement with per-slice processing at 0.0000 dB (VV and VH, 12.5 M pixels) and
−0.0011 dB (3.5 M pixels), against a 0.171 dB bound, with all products on the
record's lattice. The treatment year is more heavily assembled than any
baseline year except 2019 and 2020, so this is recorded as a known asymmetry
even though it was measured at two orders of magnitude inside tolerance.
