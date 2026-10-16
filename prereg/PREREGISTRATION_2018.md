# Pre-registration — the 2018 confirmatory test

**Written and committed before any 2016–2020 Sentinel-1 product was downloaded.**

Brian Ó Mathúna · 12 October 2026

---

## Why this document exists

The 2026 analysis produced one result below p = 0.05 out of thirty-six tests
(`METHODS_LOG.md`, *Current status*). At α = 0.05 you expect 1.8 such results by
chance, so that finding cannot stand on its own. It needs testing on data that
did not generate it.

Everything below is fixed **before** the SAR for 2016–2020 is processed. The
hypothesis, the test, the baseline membership rule, the decision thresholds and
the meaning of each outcome are all stated here in advance. If any of them is
changed afterwards, that is a new analysis and must be declared as one.

---

## The hypothesis under test

Derived from 2026, stated here as a prediction about 2018:

> In a severe drought year, the senescence slope of the **grassland-minus-forest
> cross-ratio contrast**, measured inside a drought window defined independently
> from soil moisture deficit, is **steeper** than the same quantity in
> non-drought years.

2026 measured a baseline of **−0.188 dB/month** against a drought-year value of
**−0.390 dB/month** — a ratio of **2.07**, roughly a doubling of the senescence
rate.

**2018 is the appropriate test.** It is the most severe drought in the 23-year
Oak Park record (2,308 deficit-days against 2026's 1,915; peak SMD 96.8 mm
against 96.2 mm), and Sentinel-1A and 1B were both operating, giving relative
orbit 1 the same 6-day cadence as 2021, 2025 and 2026.

---

## Fixed in advance

### Treatment and baseline membership

A **drought year** is one whose April–October deficit-days (the integral of
moderately drained SMD above 50 mm) exceeds the 90th percentile of the
2004–2026 Oak Park record. Two years qualify: **2018 and 2026**.

Every other processed year is a **baseline year**, including moderately dry ones
(2020 at 950 deficit-days, 2022 at 644). Admitting them makes the baseline
harder to beat, which is the correct direction for a confirmatory test.

Expected baseline set after processing: 2016, 2017, 2019, 2020, 2021, 2022,
2023, 2024, 2025 — **nine years**. Any year that cannot be processed, or whose
drought window holds fewer than four acquisitions, is dropped and the omission
recorded.

### The window

Derived from Met Éireann station 375 by the **same rule already in use**: the
longest spell with moderately drained SMD ≥ 50 mm lasting at least 10 days,
written to `results/phase4/drought_window_2018.json` with its rule and a
timestamp before any SAR test reads it (REQ-20).

The rule is not re-tuned for 2018. The 50 mm threshold is the Irish agronomic
convention for water-limited grassland growth and was chosen before the 2026
window was derived.

### The test

Senescence slope of the grassland-minus-forest cross-ratio contrast within the
window, each year fitted separately, baseline years pooled by random effects and
weighted by precision, 2018 compared against the resulting **prediction
interval** (REQ-22). Leave-one-out calibration reported alongside.

### Decision thresholds

With nine baseline years, df = 8 and the two-sided 5% critical value is
**t = 2.306**.

| outcome | criteria |
|:--------|:---------|
| **CONFIRMED** | 2018's slope is steeper than baseline **and** z ≤ −2.306 |
| **CONSISTENT, UNDERPOWERED** | steeper than baseline, \|z\| < 2.306, **and** the observed deviation is below the computed minimum detectable effect |
| **REFUTED** | 2018 is not steeper than baseline, **or** it is well inside the interval while the MDE shows the test had power to detect a ratio ≥ 1.5 |

### Point prediction

**slope₂₀₁₈ / baseline ≥ 1.5**, with a point estimate of **2.1** — the ratio
2026 produced. 2018 was the more severe drought, so a smaller ratio would itself
be informative.

### What is *not* part of the confirmatory criterion

**Tillage − forest is excluded**, and this is declared in advance. 2026 measured
its between-year variance at τ = 0.138 dB/month against grassland's 0.000, and
its drought window spans harvest — a structural change that dwarfs drought and
moves by weeks between years. It will be reported regardless, but it cannot
confirm or refute.

**Dry − wet grassland is secondary.** Its 2026 calibration check failed (2021 at
z = −2.23, comparable to the drought year), so it is reported as supporting
evidence only.

**σ⁰VV and σ⁰VH are reported but not confirmatory.** 2026 established the
cross-ratio as the more sensitive observable by an order of magnitude in τ.

---

## Committed in advance: both outcomes will be published

Whichever way this lands, it is reported in `TECHNICAL_REPORT.md` rev. 2 with
equal prominence.

**If confirmed:** two independent severe droughts, seven and eight years apart,
produce the same signature on a pre-specified test. The report's headline
becomes a detection with a measured effect size, and the sensitivity analysis
becomes the supporting material.

**If refuted:** the 2026 result was most likely one of the 1.8 expected false
positives. The sensitivity conclusion stands as written and is strengthened by
having been tested rather than assumed. The report keeps its current headline
and gains a section on why the 2026 result looked convincing and was not.

The second outcome is the less satisfying one and the more useful. It is being
written down now precisely so that the choice is not made after seeing which
arrived.

---

## Secondary, and not a new hypothesis

The same nine-year baseline will also be applied to **2026**, which was
previously tested against five years. This is the identical test with more
baseline data, not a new question, and both the five-year and nine-year results
will be reported.

Expect the interval to narrow: df rises from 4 to 8 and the critical value falls
from 2.776 to 2.306.

---

## Known threats, recorded before the data arrives

**Processor baseline.** Sentinel-1 IPF versions changed across 2016–2026, and
thermal-noise vectors improved. A baseline change inside the series would mimic
a trend. It cancels in a same-image spatial contrast — the same argument that
makes platform calibration irrelevant to these contrasts — but it affects the
absolute series. The IPF version per product will be recorded and reported.

**Sentinel-1B is uncalibrated** against the S1A/S1C/S1D reference (no
consecutive-day pair exists, and S1B failed three years before S1C launched).
2018 is roughly half S1B. This does not affect the contrasts, for the same
reason.

**Baseline years are unevenly sampled.** 2017–2020 are 6-day; 2022–2024 are
12-day. Precision weighting handles it; the per-year acquisition counts will be
reported.

**The window may be short.** 2018 had 102 days above 50 mm against 2026's 65, so
its window is likely longer, not shorter — but if any baseline year holds fewer
than four acquisitions inside it, that year is dropped and the drop recorded.
