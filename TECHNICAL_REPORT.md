# Detection limits of Sentinel-1 cross-ratio for drought monitoring over Irish farmland

**An eleven-year analysis, and the falsification of its own earlier result**

Brian Ó Mathúna · 16 October 2026 · rev. 2

---

## Summary

Ireland experienced a prolonged, hot drought in summer 2026. At Oak Park,
Co. Carlow it was the second most severe in the 23-year soil-moisture record,
and Teagasc measured national grass production 412 kg DM/ha below the five-year
average. This study asked whether that impact is visible in Sentinel-1 C-band
SAR over a 1,600 km² area of the Carlow tillage belt.

**It is not**, and the useful part of the study is how that conclusion was
reached.

Revision 1 of this report, based on 156 acquisitions across 2021–2026, found a
null result and quantified a detection limit. A subsequent window-restricted
analysis then produced a result at **p = 0.0398** — grassland senescence
apparently doubling during the meteorologically-defined drought period. Rather
than publish it, the hypothesis, the test, the baseline membership rule and the
decision thresholds were **pre-registered in version control**, and the archive
was extended backwards to 2016 to test it on data that had not generated it.

The archive now holds **316 acquisitions across eleven years and four
satellites**. Both treatment years fail their pre-specified tests:

| | pre-specified test | result |
|:--|:--|:--|
| **2018** (most severe drought on record) | z ≤ −2.306 and steeper than baseline | **+1.35** — flatter, wrong direction |
| **2026** (second most severe) | same test, nine-year baseline | **−1.75**, p = 0.119, inside |

2026's earlier z = −3.00, p = 0.0398 does not survive. Its slope estimate did
not change by a thousandth of a decibel; only the baseline it was compared
against changed.

**The cause is the central finding of this report.** Revision 1 reported, as its
strongest positive result, a between-year standard deviation of **zero** across
five baseline years, and read it as evidence of pipeline stability. It was not.
With five years, the DerSimonian–Laird estimator returns zero whenever
within-year sampling error accounts for the observed scatter, and the prediction
interval then collapses toward the treatment year's own standard error. Nine
years put genuine between-year variation at **±0.17 dB/month** — three times
2026's own fit error — and the effect disappears.

Worse, the decision *not* to acquire more baseline years had been justified by a
variance decomposition computed from the same five years. The argument was
circular and the data broke it.

The conclusion that stands is narrower than rev. 1's and better supported: over
this cover, at this cadence, in this observable, ordinary interannual variation
exceeds any drought signal the eleven-year record can evidence. The transferable
finding is sharper still — **a small-sample variance estimate of zero is a
warning that the baseline is too small, not a finding about the instrument.**

---

## 1. Objective, and how it changed three times

The original question was whether SAR could detect drought impact on vegetation
and support an inference about crop yields.

**First change.** Yield prediction was unavailable: the 2026 harvest was in
before analysis began and no parcel-level ground truth existed. A pre-registered
prediction against the CSO *Area, Yield and Production of Crops* release
(~1 May 2027) was substituted and the retrospective component became primary.

**Second change.** The whole-AOI aggregate could not answer the question
(§5.2), and the design moved to stratified difference-in-differences against a
baseline *distribution* rather than a reference year.

**Third change, and the one that defines this revision.** A window-restricted
test produced p = 0.0398 among thirty-six comparisons, where 1.8 such results
are expected by chance. The project's response was to treat it as a hypothesis
rather than a finding, and to go and test it.

The question actually answered:

> Given a validated Sentinel-1 processing chain and eleven years of consistent
> acquisitions, is a severe drought distinguishable from ordinary interannual
> variation — and if an earlier analysis said yes, why did it?

---

## 2. Study area and data

### 2.1 Area of interest

A 40 × 40 km square (1,600 km²) centred on E 673044.2, N 679462.2 in EPSG:2157
(IRENET95 / Irish Transverse Mercator), covering the Carlow tillage belt and
containing Met Éireann synoptic station 375 at Oak Park. Chosen for high arable
fraction and the presence of a station.

Land cover from the National Land Cover Map 2018 (EPA and Tailte Éireann),
197,134 polygons across 29 Level-2 classes. Improved Grassland 737.9 km² (46.1%)
and Cultivated Land 454.2 km² (28.4%) dominate; the three forest classes used as
control total 104.4 km².

### 2.2 Orbital configuration

Phase 0 reconnaissance evaluated every orbit and direction covering the AOI.
**Relative orbit 1, ASCENDING** was selected and frozen. Re-evaluated across the
full eleven years it remains the only viable candidate — competing orbits 74 and
103 reach minimum AOI coverage of 0.323 and 0.178 against orbit 1's 1.000. These
are not near-misses; they are the wrong swath.

Orbit 1 also offers an evening overpass (~19:15 local), avoiding morning dew.

### 2.3 Acquisitions

**316 acquisitions, April–October, 2016–2026.** All verified; none excluded.

| era | years | acquisitions | assembled from 2 slices | cadence |
|:--|:--|---:|---:|:--|
| extension | 2016–2020 | 157 | 120 | 12-day, then 6-day from 2017 |
| original | 2021–2026 | 159 | 1 | mixed 6/12-day |

Products: Sentinel-1 IW GRDH, dual polarisation VV+VH, from the Copernicus Data
Space Ecosystem. Approximately 760 GB acquired.

**Constellation.** Four platforms. Sentinel-1A from 2014 to termination on
29 June 2026; Sentinel-1B from 2016 to its December 2021 failure; Sentinel-1C
and 1D entering service in 2025 and 2026. Platforms interleave within seasons
rather than switching at a handover, permitting same-season inter-platform
comparison (§4.2).

### 2.4 Drought severity ranking

From Met Éireann station 375, deficit-days computed as the April–October
integral of moderately drained soil moisture deficit above 50 mm:

| year | peak SMD | deficit-days | role |
|:--|---:|---:|:--|
| **2018** | 96.8 mm | **2,308** | treatment |
| **2026** | 96.2 mm | **1,915** | treatment |
| 2020 | 80.0 | 950 | baseline |
| 2022 | 73.6 | 644 | baseline |
| 2023 | 76.6 | 476 | baseline |
| 2025 | 66.1 | 254 | baseline |
| 2019 | — | 164 | baseline |
| 2021 | 60.4 | 115 | baseline |
| 2016, 2017, 2024 | — | < 100 | baseline |

A drought year is defined as one exceeding the 90th percentile of the 2004–2026
record. Exactly two qualify. This rule was fixed before the extended archive was
processed.

---

## 3. Processing chain

Executed headless via SNAP `gpt` from version-controlled graphs.

**Single-slice acquisitions (195 of 316), graph v3:**

```
Read → Apply-Orbit-File → ThermalNoiseRemoval → Remove-GRD-Border-Noise
     → Calibration → Subset → Terrain-Correction → Write
```

**Assembled acquisitions (121 of 316), graph v4** — two per-slice branches
joined before the shared tail:

```
Read  → Apply-Orbit-File  → ThermalNoiseRemoval  ┐
                                                  ├→ SliceAssembly →
Read2 → Apply-Orbit-File2 → ThermalNoiseRemoval2 ┘
     → Remove-GRD-Border-Noise → Calibration → Subset → Terrain-Correction
```

Graph v3 is **byte-identical** across the whole archive, including every scene
processed before assembly existed, so "the processing chain did not change" is a
fact about the files rather than an argument. v4 was generated programmatically
from v3 and verified node by node: branch 1 and everything from
`Remove-GRD-Border-Noise` onward identical, branch 2 an exact copy reading a
second input, and exactly one node changed — the border-noise node's source.

Decisions worth stating:

**σ⁰ is stored and averaged in linear power, not dB.** The mean of a logarithm
is not the logarithm of a mean. On a scene half bright and half dim the correct
answer is −12.6 dB and the dB-averaged answer is −15.0 dB: a 2.4 dB bias in the
same direction every time, against a signal expected at 1–3 dB.

**Negative values are retained** (`clipNegativeValues=false`). After thermal
noise subtraction the noise-floor estimate is unbiased but noisy; discarding the
negative tail biases every mean upward, most severely in VH, the channel closest
to the noise floor and the one carrying the signal.

**Precise orbits are mandatory** (`continueOnFail=false`).

**`alignToStandardGrid=true`.** With the flag off, every acquisition lands on
its own 10 m lattice and no two rasters stack without resampling. Harmless to
per-scene checks; fatal to a time series. See NCR-12.

**Border-noise removal follows assembly, not precedes it.** Run per slice it
would trim the along-track edges that become the interior seam, cutting a gap
into the middle of the product.

Output: 10 m pixels, EPSG:2157, bands `Sigma0_VV`, `Sigma0_VH`,
`projectedLocalIncidenceAngle`.

---

## 4. Method

### 4.1 Per-scene verification

Every scene passed an automated gate before entering the archive: band presence,
CRS and pixel geometry, AOI containment **against the valid-data mask rather
than the bounding box**, σ⁰ plausibility and linearity. Raw products were
deleted only after verification passed, so a failed scene retains its input and
logs the reason.

**316 of 316 verified. 100.0% valid-pixel fraction on every band of every
scene.**

### 4.2 Inter-platform calibration (REQ-09)

Relative orbit 1 contains two consecutive-day, different-platform pairs sharing
S1C, triangulating onto a common reference:

| pair | σ⁰VV | σ⁰VH | cross-ratio |
|:--|---:|---:|---:|
| S1D − S1C (23/24 Apr 2026) | −0.070 dB | −0.171 dB | −0.101 dB |
| S1A − S1C (28/29 Jun 2026) | +0.147 dB | +0.035 dB | −0.112 dB |

Projected local incidence angle across all four scenes spans 0.08°, roughly
0.01 dB of geometric variation — viewing geometry is excluded as an explanation.

**Largest single-channel offset 0.171 dB. The cross-ratio is better calibrated
than either channel forming it**, the two independent pairs agreeing to
**0.011 dB** against a 0.22 dB spread across individual channels, because a gain
error common to both polarisations cancels exactly in a ratio.

*Caveat.* One day of real surface change sits inside every number here. These
are working upper bounds; their agreement across two seasons is what makes them
credible.

**Sentinel-1B is uncalibrated** against this reference — S1A and S1B flew the
same track six days apart, never one, and S1B failed three years before S1C
launched. Immaterial to the contrasts (§4.5), material to the absolute series.

### 4.3 Slice assembly and its acceptance test

Sentinel-1 records continuously and ESA cuts the strip into fixed-length files
for distribution. On relative orbit 1 that cut falls across the AOI throughout
2016–mid-2020: the best single slice covers **0.8232** of it, stable to four
decimal places across every affected date — a fixed grid, not a drifting one.

The original pipeline excluded such dates, which removed **every acquisition in
2018, 2019 and 2020** — the entire confirmatory test. No alternative orbit
exists. Assembly was therefore implemented (NCR-17).

The slices are one pass, not two: same platform, same absolute orbit, same
datatake, with slice 1 ending at the instant slice 2 begins. The cut is a
packaging boundary applied on the ground to continuous data, which is why
rejoining it is lossless.

**Acceptance test, specified before the capability was built.** An assembled
scene must land on the archive's shared lattice, and must agree with each of its
own slices processed independently, over that slice's own ground, to better than
the 0.171 dB established independently in §4.2. Measured on 2018-07-04:

| comparison | σ⁰VV | σ⁰VH | cross-ratio | pixels |
|:--|---:|---:|---:|---:|
| assembled vs the 0.8232 slice | +0.0000 dB | −0.0000 dB | −0.0001 dB | 12,482,448 |
| assembled vs the 0.1766 slice | −0.0011 dB | −0.0011 dB | +0.0000 dB | 3,506,460 |

Two orders of magnitude inside tolerance. The agreement is this close because
each slice is noise-corrected independently before being joined, so over each
slice's own ground the assembled scene is the same arithmetic rather than an
approximation of it.

The southern residual of −0.0011 dB is **identical in VV and VH**, so the
cross-ratio cancels to +0.0000 — an incidental but direct measurement of the
common-mode cancellation the entire design rests on.

### 4.4 Processor-baseline provenance

Thermal-noise vectors and calibration tables change between IPF releases. A
uniform offset cancels in a same-image spatial contrast; a change *within* a
year does not cancel in that year's slope fit, and has the same shape as a
vegetation signal.

The archive spans **21 IPF versions, 002.62 to 004.03**. Restricted to the
analysis fit range, both treatment years sit on a single baseline, as do seven
of the nine baseline years. 2016 (2.71→2.72) and 2017 (2.82→2.84) change within
the limb; neither crosses 002.90 or 003.10, the releases where noise handling was
reworked. Both were retained, with the judgement and its overturning condition
recorded in advance (Amendment 2).

An absolute offset of roughly 0.5 dB is visible in the whole-AOI aggregate for
2016 and 2017, the two oldest-baseline years — a worked demonstration of why the
design uses a contrast rather than absolute σ⁰.

### 4.5 Statistical design

The stratified estimator:

```
effect = (grass − forest)treatment − (grass − forest)baseline distribution
```

The inner subtraction removes weather. A forest and the field beside it receive
the same rain on the same night, imaged in the same pass by the same satellite
at the same incidence angle through the same atmosphere. Every nuisance term is
common and cancels — including platform calibration and processor baseline.

The outer subtraction removes everything permanent.

Three contrasts: grassland−forest and tillage−forest share a control and are
correlated; dry−wet grassland involves no forest and is independent of both.

**The test is a prediction interval, not a confidence interval.** The question
is not whether the treatment year differs from the average normal year but
whether it could *be* a normal year, so the interval must include the genuine
spread of normal years (τ², DerSimonian–Laird) plus the treatment year's own fit
error. Baseline years are weighted by precision.

**Leave-one-out calibration** tests each baseline year against the others. Those
years are normal by assumption, so this measures what |z| a normal year
produces. A test that cannot clear its own null is reported as such.

### 4.6 Pre-registration

The 2018 test was specified in full before any 2016–2020 product was
downloaded, and committed to a public repository:

| document | date | content |
|:--|:--|:--|
| `prereg/PREREGISTRATION_2018.md` | 12 Oct | hypothesis, baseline membership rule, decision thresholds, meaning of each outcome, commitment to report either |
| Amendment 1 | 13 Oct | fit range = window ∩ senescence limb; effect-size prediction withdrawn; level test promoted to co-primary |
| Amendment 2 | 15 Oct | IPF observation recorded; no test changed; overturning condition stated |

The analysis window came from Met Éireann soil-moisture deficit by a rule fixed
before the 2026 window was derived, written with its rule and a timestamp, and
committed **before the imagery existed on disk**. Amendment 1 was made before
any stratified series had been computed; Amendment 2 before any test had been
run on the extended archive.

Both amendments state, in advance, what would overturn their own decisions.

---

## 5. Results

### 5.1 Pipeline validation

316 of 316 scenes verified, 100.0% valid-pixel fraction throughout, and **all
316 share one pixel lattice** `(EPSG:2157, 10.0, 10.0, 5.0, 5.0)` — including
every one of the 121 assembled scenes. `build_series.py` refuses to write a
mixed stack, so this is a gate rather than a report.

Seasonal phenology reproduces independently in all eleven years.

### 5.2 Whole-AOI aggregate — null, and why it was abandoned

Day-of-year matched pairs, 2026 against 2025, June–September:

| metric | difference | p |
|:--|---:|--:|
| σ⁰VV | −0.080 dB | 0.58 |
| σ⁰VH | −0.045 dB | 0.78 |
| cross-ratio | +0.036 dB | 0.39 |

**The standard deviation of those matched-pair differences is 0.63 dB.** With 16
million pixels averaged, speckle is negligible; this is real geophysical
variability dominated by soil wetness at overpass. It sets a detection floor
near 0.4 dB for any aggregate approach.

### 5.3 The pre-registered 2018 test — refuted

Grassland − forest, cross-ratio slope, fit range DOY 182–253, against nine
baseline years:

| year | slope (dB/month) | n | r² |
|:--|---:|---:|---:|
| 2016 | +0.069 ± 0.159 | 6 | 0.05 |
| 2017 | −0.046 ± 0.069 | 12 | 0.04 |
| 2019 | −0.189 ± 0.073 | 12 | 0.40 |
| 2020 | +0.118 ± 0.111 | 12 | 0.10 |
| 2021 | −0.208 ± 0.065 | 12 | 0.51 |
| 2022 | −0.067 ± 0.087 | 6 | 0.13 |
| 2023 | −0.175 ± 0.222 | 6 | 0.13 |
| 2024 | −0.144 ± 0.037 | 5 | 0.83 |
| 2025 | −0.140 ± 0.063 | 12 | 0.33 |
| **baseline** | **−0.116**, between-year sd 0.043 | | |
| 95% prediction interval | [−0.395, +0.163] | | |
| **2018** | **+0.047 ± 0.109** | 12 | 0.02 |
| | **z = +1.35, p = 0.215** | | |

The pre-specified rule required 2018 to be *steeper* than baseline **and**
z ≤ −2.306. It is flatter, and the sign is positive. The test fails on direction
before significance is reached, so no power argument applies — the estimate is
on the wrong side of the baseline, not merely close to it.

**By the rule written on 12 October: REFUTED.**

**The co-primary level test disagrees**, and Amendment 1 fixed in advance that
such a disagreement is itself the finding, not something to be resolved by
preferring the more favourable. At DOY 227, 2018 sits below baseline in all
three contrasts (z = −2.53, −3.27, −2.03) and its slopes are flatter in all
three. The pattern is coherent: 2018 was already low, and flat.

Its calibration nonetheless fails — on grassland−forest the most extreme
*baseline* year is 2017 at z = +3.37, further from the baseline than 2018.

### 5.4 2026 re-tested on nine baselines — refuted

The original pre-registration committed to re-running 2026 against the wider
baseline, as the identical test with more data rather than a new question.
Fit range DOY 183–240, 2026's own frozen window:

| | rev. 1 configuration | this revision |
|:--|---:|---:|
| baseline years | 5 (2021–2025) | 9 (2016–2025 less treatment years) |
| pooled baseline | −0.188 | −0.055 |
| between-year sd (τ) | **0.000** | **0.169** |
| 2026 slope | −0.390 ± 0.060 | −0.390 ± 0.060 |
| z | −2.99 | **−1.74** |
| p | 0.040 | **0.119** |
| verdict | outside | **inside** |

**2026's estimate is identical to a thousandth of a decibel in both rows.**
Nothing about the treatment year changed. The earlier significance came entirely
from the baseline it was measured against.

The co-primary level test likewise places 2026 inside on all three contrasts
(z = −2.16, −1.38, −1.24), each with a baseline year further out than 2026.

### 5.5 Where the earlier result came from

| baseline set | k | pooled | τ | z | p | |
|:--|---:|---:|---:|---:|---:|:--|
| **9 years (pre-specified)** | 9 | −0.055 | 0.169 | −1.74 | 0.119 | inside |
| 7, dropping 2016 + 2017 | 7 | −0.086 | 0.173 | −1.53 | 0.177 | inside |
| 8, dropping **2020** | 8 | −0.141 | 0.058 | −2.71 | 0.030 | outside |
| 5, the original 2021–2025 | 5 | −0.188 | **0.000** | −2.99 | 0.040 | outside |

**The result rests on a single year.** 2020's grassland−forest slope is
**+0.454 ± 0.112** where most years are negative. Including it raises the
between-year sd from 0.058 to 0.169 and moves the pooled baseline from −0.141 to
−0.055; both changes place 2026 inside. The original five-year baseline was
2021–2025, which excludes 2020. That omission is the whole difference between
p = 0.04 and p = 0.12.

Dropping the two processor-baseline-flagged years instead *weakens* the result
further, which answers Amendment 2's question: the IPF years are not the source
of the extra variance.

### 5.6 Calibration fails in every primary cell

Across both runs — twelve primary cells — **every one reports a baseline year
further from the baseline than the treatment year**: 2020 at z = +4.50, 2017 at
z = +3.37, 2021 at z = −2.39, 2022 at z = −2.28, 2016 at z = +1.74.

This is the clearest single statement the study can make about its own
sensitivity. The prediction intervals are not wide enough to call any year
unusual, and the method cannot presently distinguish a record drought from an
ordinary summer.

---

## 6. Discussion

### 6.1 NCR-18 — a variance estimate of zero is a warning, not a finding

Revision 1 stated: *"τ = 0.000 for grassland−forest is the strongest positive
result in this study. Five independent years, spanning four different platform
combinations, produce senescence slopes that are statistically
indistinguishable."*

**That reading was wrong.** With k = 5, the DerSimonian–Laird estimator returns
τ² = 0 whenever within-year sampling error accounts for the observed scatter —
Q falls below its expectation and the estimator truncates at zero. The
prediction interval then collapses toward the treatment year's own standard
error, and a tight interval produced by too few years is indistinguishable from
one produced by a stable measurement.

Nine years give τ = 0.169, against 2026's own fit error of 0.060. Between-year
variation is three times the within-year precision, which is the opposite of
what rev. 1 concluded.

**The compounding error.** The project's own planning document listed additional
baseline years under *explicitly not worth doing*, citing a variance
decomposition attributing 82% of uncertainty to the treatment year's fit error
and 0% to between-year variation. That decomposition was computed from the same
five years that produced the artefact. The argument was circular, and only
acquiring the data could break it.

**Classification.** A method error — the second in the project after NCR-14, and
of the same family: a statistic computed correctly and interpreted as something
it is not.

**Transferable rule.** Any estimator that can return exactly zero should be
interrogated when it does. In a random-effects design on a short environmental
record, τ² = 0 from fewer than roughly ten groups should be treated as
"insufficient data to estimate between-group variance", never as "no
between-group variance".

### 6.2 The single-baseline trap, four occurrences

| occurrence | against one year | against the distribution |
|:--|---:|---:|
| VH tillage (rev. 1) | p = 0.046 | p = 0.20 |
| Level DiD, dry−wet (rev. 1) | p = 0.0087 | not significant |
| 2026 slope, grassland−forest | p = 0.0153 | p = 0.119 |
| 2026 slope, dry−wet | p = 0.0029 | p = 0.081 |

Four independent instances in one dataset, each the same measurement read
against a different comparator. The cause is visible in §5.3: an individual
baseline year can sit anywhere in a ±0.17 dB/month spread, and comparing against
one of them inherits wherever it happened to fall.

A single-baseline design cannot detect this failure from within itself.

### 6.3 A control works by being similar, not by being inert

Per-year slope precision in the 2018 run:

| contrast | SE (dB/month) | pixels |
|:--|---:|---:|
| tillage − forest | 0.223 | 3,517,523 |
| grassland − forest | 0.109 | 4,380,843 |
| **dry − wet grassland** | **0.052** | **154,972** |

The dry−wet contrast is **twice as precise as grassland−forest on a thirtieth of
the pixels**. Pixel count is not the limiting factor; the correlation between
treatment and control nuisance response is.

Dry and wet grassland respond almost identically to wind, dew, rainfall and
overpass geometry, differing mainly in drainage, so their difference is quiet.
Grass and forest differ in nearly everything, so their difference inherits all
of it — and forest canopy is not a still reference, its backscatter moving with
wind and canopy water independently of the ground.

This finding is unchanged from rev. 1 and reproduces on the wider archive.

**Design implication:** when selecting a control stratum for SAR change
detection, maximise the correlation of nuisance response between treatment and
control, not the control's insensitivity to the treatment effect.

### 6.4 2020

**2020 had 950 deficit-days — the third most severe drought in the 23-year
record — and the shallowest grassland−forest slope in the entire series, in the
direction opposite to the hypothesis.**

Two readings, neither helpful. Either the measurement is too noisy at this
precision for 2020 to mean anything, in which case it is too noisy for 2026
either. Or 2020 is real, and the relationship between drought severity and
senescence rate in this observable is not there.

An eleven-year record with a dose–response structure would distinguish these.
Three severity levels (2018 and 2026 severe, 2020 moderate, the rest ordinary)
and no monotonic ordering in the response is weak evidence against the
hypothesis independent of any significance test.

### 6.5 A post-hoc hypothesis, raised and not pursued

2018's drought window opens on DOY 151 and the fit begins at 182, so 31 days of
drought sit outside the fitted range. "Already low, now flat" is exactly what
would be seen if senescence had occurred before the fit began — a physically
coherent story, and in 2018 the drought did begin a month earlier than in 2026.

**It is not pursued here.** The idea arrived after the result. Amendment 1
excluded DOY 151–181 for a stated reason, before the data existed, and that
reasoning did not become wrong because the answer disappointed. Refitting 2018
over its full window now would be fitting the test to the answer.

If the idea is worth pursuing it must be pre-registered and tested on a year not
yet used. It is recorded here so that a future analysis has a dated origin for
it.

### 6.6 Why the drought is not visible

Teagasc measures dry matter accumulated over a season. The SAR cross-ratio
responds to canopy structure at the instant of overpass. A sward under water
stress grows less but need not become structurally different enough, at 5.4 cm
wavelength, to move volume scattering measurably — particularly when grazing and
cutting impose far larger structural changes on the same fields.

The aggregate result adds a second reason: the per-overpass soil-moisture term
(0.63 dB) exceeds any plausible seasonal drought term. The stratified contrast
removes most of it; what remains still dominates.

---

## 7. Superseded results

Preserved rather than deleted, because they are the evidence for §6.1.

| rev. 1 claim | status |
|:--|:--|
| "τ = 0.000 … the strongest positive result in this study" | **Superseded.** A small-sample artefact; see NCR-18. |
| Detection limit 81% of baseline senescence rate, observed 38% | **Superseded.** Computed against a baseline whose variance was underestimated. |
| Variance decomposition: 0.0% between-year | **Superseded.** Between-year sd is 0.169 dB/month on nine years. |
| "Additional baseline years barely help" | **Refuted.** They reversed the conclusion. |
| 2026 window result z = −3.00, p = 0.0398 | **Refuted** on nine baselines: z = −1.74, p = 0.119. |
| Control similarity dominates control inertness | **Stands**, reproduced on the wider archive. |
| Inter-platform agreement 0.171 / 0.011 dB | **Stands.** |
| Whole-AOI noise floor 0.63 dB | **Stands.** |

---

## 8. Limitations

1. **Slope fits are poor.** Several years return r² below 0.1, including 2018 at
   0.02. The cross-ratio over this range is not linear enough for a slope to be
   a stable summary — which is why Amendment 1 promoted the level test to
   co-primary, and why slope and level disagree for 2018.
2. **Slope and level disagree for 2018** and the disagreement is unresolved.
   Reported as a finding, per Amendment 1.
3. **2016 and 2017 carry a processor-baseline change inside the fit range.**
   Neither crosses a thermal-noise epoch; both retained. Dropping them does not
   change any conclusion.
4. **Baseline years are unevenly sampled** — 5 to 12 limb acquisitions.
   Precision weighting mitigates but does not remove this.
5. **Sentinel-1B is uncalibrated** against the S1A/S1C/S1D reference. Immaterial
   to the contrasts, material to the absolute series for 2016–2021.
6. **Land cover is 2018**; tillage parcels rotate, so the tillage stratum carries
   genuine label error that dilutes toward finding nothing.
7. **Single AOI, single orbit.** Generalisation beyond south-east Irish mixed
   farmland is not supported.
8. **Two treatment years is a small sample for a confirmatory design.** Only two
   years in the Sentinel-1 era exceed the severity threshold, and both are now
   used.

---

## 9. Conclusions

1. The 2026 drought is **not detectable** in Sentinel-1 cross-ratio over this
   AOI, and neither is the more severe 2018 drought, on a pre-specified test
   against a nine-year baseline.
2. **An earlier result at p = 0.0398 does not replicate** and was refuted by the
   same analysis extended to nine baseline years, with the treatment-year
   estimate unchanged.
3. **The cause was a small-sample variance artefact.** A between-year standard
   deviation of zero from five years was read as instrument stability; it was a
   truncated estimator. Nine years give ±0.17 dB/month (NCR-18).
4. **The decision not to acquire more baseline data had been justified
   circularly**, from a variance decomposition computed on the years that
   produced the artefact.
5. **Ordinary interannual variation exceeds any drought signal** this record can
   evidence. Every calibration check across twelve primary cells finds a
   baseline year more extreme than the treatment year.
6. **The third-most-severe drought in the record moves opposite to the
   hypothesis**, which is weak evidence against it independent of significance.
7. Inter-platform radiometric consistency across S1A/S1C/S1D is **0.171 dB worst
   channel and 0.011 dB in the cross-ratio**; the constellation can be treated
   as one instrument for this purpose.
8. **GRD slice assembly reproduces per-slice processing to 0.0000 dB** over
   12.5 M pixels, and all 316 acquisitions share one pixel lattice.
9. In difference-in-differences SAR designs, **control similarity dominates
   control inertness** — demonstrated at a factor of two on a thirtieth of the
   pixels.

### Standing commitment — the pre-registered external check (REQ-14)

**Due ~1 May 2027, when the CSO publishes *Area, Yield and Production of Crops*
for the 2026 crop year.** Before that date and committed to the repository with
a timestamp: the predicted direction and magnitude of the 2026 yield anomaly,
with its reasoning, stated as a prediction of an *unpublished measurement* and
never as a prediction of a future event.

This survives the refutation and is sharpened by it. The SAR record cannot
resolve the drought effect, so the honest prediction is now a statement about
detection limits rather than about yield — and it is checkable against a number
this project has no influence over. A null result that still makes a falsifiable
external commitment is worth more than one that quietly stops.

### Recommended future work

- **Pre-register a dose–response design**: regress the contrast on soil moisture
  deficit directly rather than testing a binary window. Uses the whole series,
  and would resolve §6.4 one way or the other.
- **Pre-register the early-onset hypothesis** (§6.5) and test it on a year not
  used here.
- **Sentinel-2 NDVI over identical strata.** If optical resolves what SAR cannot,
  the detection-limit result gains a direct reference point.
- **A drainage-stratified grassland control**, following §6.3 — same crop, same
  management, differing water-holding capacity.

---

## 10. Engineering record

**Eighteen nonconformances** raised and closed. **Two were method errors**
(NCR-14, NCR-18); the remaining sixteen were configuration, packaging, labelling
or environment.

| class | character |
|:--|:--|
| Correct computation, wrong presentation | labelling, unit and diagnostic errors on arithmetic already right — seven of eighteen |
| Configuration and environment | a GUI default, a missing preflight, a stale manifest, a flag left false |
| Unasserted batched edits | patches that silently matched nothing |
| Data-configuration constraints | REQ-17's multi-slice exclusion removing the entire confirmatory year |
| **Method** | NCR-14 (slope test mis-specified for a non-linear observable), NCR-18 (τ = 0 misread) |

Four are worth singling out.

**NCR-12** (`alignToStandardGrid=false`) was invisible to every per-scene check
and to a passing test suite, because it manifests only when scenes are stacked.
It was found by a tool written to measure something else — the
cross-calibration script had to align two rasters and reported the misalignment
as a by-product.

**NCR-17** (REQ-17 removing the confirmatory year) was latent for six years
because the AOI happened to fall inside a single slice throughout the era first
processed. Three bugs in its replacement survived a full suite of hand-written
tests and died within seconds of meeting the real 604-product catalogue: the
fixtures encoded the same assumptions as the code.

**The SNAP refusal.** The first assembly design was rejected by the operator
itself — *"Noise removal should be applied prior to slice assembly"* — because
thermal-noise tables are indexed per slice. A tool declining to do something is
information; no amount of code review would have surfaced that constraint.

**NCR-18**, discussed in §6.1, is the only nonconformance in the project that
changed a published conclusion.

**The pattern:** the failure mode was never the radar. It was configuration,
packaging, labelling, environment — and, twice, the interpretation of a
correctly computed statistic. Every defence that worked is a check on plumbing
or on reasoning, not on physics.

**405 automated tests**; CI on Python 3.11 and 3.13.

### Data-engineering record

| | |
|:--|:--|
| Volume acquired | ~760 GB |
| Pipeline state | manifest-per-acquisition, written immediately; resumable |
| Interruptions survived | 2 (one unexplained process termination, one API throttling event) |
| Acquisitions recovered by retry policy | 5, including the whole of September 2018 |
| Catalogue duplicates removed | 166 products across 83 dates |
| Source API resilience | backoff extended from 15 s to 16 min across six attempts; connect and read timeouts separated; post-failure cooldown |

---

## 11. Reproducibility

| artefact | path |
|:--|:--|
| Processing graphs | `graphs/s1_grd_preprocess_v3.xml`, `v4.xml` |
| Acquisition catalogue | `S1_Recon/recon_out/scenes.csv` |
| Reconnaissance | `S1_Recon/s1_recon.py` |
| Slice planning | `S1_Recon/slices.py` |
| Batch runner | `S1_Recon/batch_process.py` |
| Per-scene verification | `S1_Recon/verify_scene.py` |
| Assembly acceptance test | `S1_Recon/check_assembly.py` |
| Processor-baseline audit | `S1_Recon/ipf_check.py` |
| Cross-calibration | `S1_Recon/crosscal.py` |
| Time series | `S1_Recon/build_series.py` |
| Meteorology and window freeze | `S1_Recon/fetch_met.py` |
| Land cover | `S1_Recon/fetch_landcover.py` |
| Stratified analysis | `S1_Recon/stratify.py` |
| Pre-registration | `prereg/` — pre-registration + Amendments 1, 2 |
| Methods log | `METHODS_LOG.md` |
| Plan and nonconformance log | `PROJECT_PLAN.md` |
| Results | `results/phase0/` … `phase4/` |

Raw Sentinel-1 products are not committed (REQ-16); the manifest is, and is
sufficient to re-derive the archive. The catalogue is retained in version
history because the CDSE catalogue is not static.

**The pre-registration's value is in the commit history.** Every decision in the
confirmatory test is dated earlier than the data that answered it, and that is
checkable by anyone who clones the repository.

**Data sources.** Copernicus Sentinel-1 data 2016–2026, processed by ESA,
retrieved from the Copernicus Data Space Ecosystem. National Land Cover Map of
Ireland 2018 © Tailte Éireann and the Environmental Protection Agency, CC BY 4.0.
Daily climate data © Met Éireann, CC BY 4.0. Grass production figures from
Teagasc PastureBase Ireland.

---

*Processing performed with ESA SNAP 14. Analysis in Python (rasterio, pyproj,
shapely, numpy, scipy).*
