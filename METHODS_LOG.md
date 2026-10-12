# Methods log — SAR drought 2026

**A chronological record of why the method changed, and what forced each change.**

Brian Ó Mathúna · last updated 12 October 2026

---

## What this document is for

`PROJECT_PLAN.md` states the requirements. `TECHNICAL_REPORT.md` states the
method as it finally stands and what it found. Neither records how it got
there — and in this project that history carries most of the transferable
content, because the analysis was re-specified six times and three of those
re-specifications overturned a result that had already been written down.

This log keeps the superseded results. They are the evidence for why the method
changed, and deleting them would make every change look like it arrived by
foresight rather than by being forced.

Nonconformances are logged in `PROJECT_PLAN.md` §15 and are referenced here by
number rather than repeated. Two copies of the same record is how NCR-11
happened.

---

## Timeline

| date | milestone |
|:-----|:----------|
| 7 Sep 2026 | Project framed. Phase 0 reconnaissance begun. |
| 8 Sep | Orbit 1 ASCENDING selected and frozen. Catalogue: 2024–2026. |
| 17 Sep | First scene processed and verified end to end. |
| 20 Sep | Cross-calibration pairs processed; REQ-09 closed. |
| 27 Sep | Graph v3 (NCR-12). 83 acquisitions, 2024–2026, batch complete. |
| 2 Oct | Aggregate time series. Null. |
| 3 Oct | Land cover fetched; stratified difference-in-differences built. |
| 3 Oct | Catalogue extended to 2021–2026. 156 acquisitions. |
| 4 Oct | Five-year baseline. Null. Technical report rev. 1 drafted. |
| 5 Oct | VV and VH re-run. NCR-14 found. Level test added. Still null. |
| 11 Oct | Met Éireann SMD fetched; drought window derived and frozen. |
| 11 Oct | Window-restricted test. First result below p = 0.05. |

---

## Six re-specifications

### 1. Crop-yield prediction → hindcast plus pre-registration

*Date:* 7 September. *Status:* settled.

The original question — would the drought affect crop yields — was not
answerable as posed. The 2026 harvest was already in, and no parcel-level
ground truth existed against which a prediction could be scored.

The pre-registration target initially chosen (a Teagasc fodder survey) was
found to have **already published** by 9 September, which would have made any
"prediction" retrospective. Moved to the CSO *Area, Yield and Production of
Crops* release, which publishes around 1 May of the following year.

*What it cost:* the headline question. *What it bought:* a question the data
could actually answer, and an honestly dated pre-registration.

### 2. Whole-AOI aggregate → stratified difference-in-differences

*Date:* 2 October. *Status:* settled.

The aggregate test compared 2026 against 2025 over the whole 1,600 km² AOI.

| test | result |
|:-----|-------:|
| σ⁰VV, 19 day-matched pairs | −0.080 dB, p = 0.58 |
| σ⁰VH | −0.045 dB, p = 0.78 |
| cross-ratio | +0.036 dB, p = 0.39 |

The decisive number was not any of those. It was the **standard deviation of
the matched pair differences: 0.63 dB.** With 16 million pixels averaged,
speckle is negligible, so that is real geophysical variability — soil wetness
on the morning of each overpass. It sets a detection floor near 0.4 dB, and it
is larger than any plausible seasonal drought term.

The aggregate was measuring weather with drought buried inside it.

*The fix:* contrast a responsive cover against a control imaged in the same
pass. A forest and the field beside it get the same rain on the same night from
the same satellite at the same incidence angle, so every nuisance term is
common to both and cancels in the subtraction.

*A consequence worth stating:* platform calibration cancels for free in a
same-image spatial contrast. REQ-09 remains necessary for the absolute series,
but the headline result does not rest on it.

### 3. One baseline year → a baseline distribution

*Date:* 3–4 October. *Status:* settled. **The most instructive change.**

With 2025 as the sole reference year, the stratified analysis produced six
estimates, all negative, with 2026 the steepest in all three contrasts. It
looked like a coherent pattern.

Adding 2021, 2022 and 2023 destroyed it:

| contrast (cross-ratio slope) | vs 2025 alone | vs 5-year baseline |
|:-----------------------------|--------------:|-------------------:|
| tillage − forest | −0.396 dB/mo | **+0.003 dB/mo** |
| grassland − forest | −0.158 | −0.069 |

The cause is visible in the baseline years themselves:

| contrast | 2021 | 2022 | 2023 | 2024 | **2025** |
|:---------|-----:|-----:|-----:|-----:|---------:|
| grassland − forest | −0.212 | −0.190 | −0.023 | −0.183 | **−0.120** |
| tillage − forest | −1.153 | −0.652 | −0.438 | −0.869 | **−0.539** |

**2025 was among the shallowest baseline years available in both contrasts.**
Comparing 2026 against it alone inflated the apparent effect — through no error
of method, simply an unlucky reference.

This is a failure mode a single-baseline design cannot detect from inside
itself. It recurred later: a VH result at p = 0.046 against 2025 alone became
p = 0.20 against the five-year baseline.

*What it cost:* one evening of downloading, 73 additional scenes.
*What it bought:* the ability to ask "could 2026 be a normal year" rather than
"does 2026 differ from one particular year".

### 4. Confidence interval → prediction interval, plus a calibration check

*Date:* 4 October. *Status:* settled.

Testing against the *mean* of the normal years answers the wrong question. The
question is not whether 2026 differs from the average normal year but whether
2026 could **be** a normal year, so the interval must include the genuine
spread of normal years (τ², estimated by DerSimonian–Laird separately from
fitting error) plus the drought year's own fit error — not merely the
uncertainty in where the baseline centre sits.

Baseline years are weighted by precision, because limb sampling ranges from 4
to 15 acquisitions and counting them equally would let the weakest fits steer
the result.

Added at the same time: a **leave-one-out calibration check**. Each baseline
year is tested against the other four. Those years are normal by assumption, so
this measures what |z| a normal year produces. It has since flagged several
tests as having no discriminating power — including one that had already been
reported in conversation.

*What it bought:* a test that can fail its own null audibly instead of silently.

### 5. Slope → level at a common reference day

*Date:* 5 October. *Status:* settled. See NCR-14.

Running the analysis on σ⁰VV and σ⁰VH exposed a defect that the cross-ratio had
concealed. **2024 came out as the extreme outlier in all six VV/VH slope
tests**, reaching z = −4.75, and every calibration check failed.

The cause: 2024 carries a 24-day gap across 1 July, so its senescence limb is
**60 days beginning on day 202**, while every other year spans 84 days from
about day 185. And the limb trajectory is not a straight line —

| observable | mean r² of a linear fit, six years |
|:-----------|-----------------------------------:|
| cross-ratio | 0.51 |
| σ⁰VV | 0.34 |
| σ⁰VH | 0.21 |

Fitting a line to a different arc of a curve returns a different gradient.
Restricting all six years to 2024's window moved the fitted slopes by sd
**0.323 dB/month**, against a between-year spread of **0.256**:

> **The artefact was larger than the quantity being measured.**

The same restriction moves the *level at a common day* by sd 0.066 against a
between-year spread of 0.540 — roughly an eighth.

*The fix:* evaluate each year's fit at day 227, within six days of every year's
mean sampling date. At the sampling centroid the prediction reduces to the mean
level and its error to the standard error of the mean, so the estimate barely
depends on the regression being right.

*Confirmation the fix worked:* 2024 was the flagged outlier in all three VH
slope tests and in **none** of the VH level tests — tested on data the fix was
not designed against.

*Why the cross-ratio escaped:* it is the one observable that is near-linear
through the limb. The error was always present; only the cross-ratio's
linearity kept it from doing damage.

### 6. Cross-ratio only → three observables

*Date:* 5 October. *Status:* settled. Prompted by literature, not by data.

Van Emmerik et al. (2022, *Remote Sensing* 14:2435) report 1–2 dB VV and VH
reductions during the 2018 Netherlands drought — and note that potato and sugar
beet showed minimal **cross-ratio** change "as VH and VV polarisations dropped
similarly". The cross-ratio is blind by construction to a common-mode drop.

The entire stratified analysis had been built on that one observable.

**The worry proved wrong, and usefully so.** Re-running on all three put the
cross-ratio as the *most* sensitive, not the least:

| contrast | σ⁰VV | σ⁰VH | cross-ratio |
|:---------|-----:|-----:|------------:|
| grassland − forest | z = −0.33 | −0.49 | **−1.75** |
| tillage − forest | −1.34 | −1.53 | **−1.67** |
| dry − wet grassland | −0.08 | −0.88 | **−1.13** |

The reason is in τ: for grassland − forest it is **0.035 dB** in the cross-ratio
against **0.496 dB** in σ⁰VV. Soil moisture makes the single channels wander
half a decibel between years; the ratio cancels it. What makes the cross-ratio
blind to common-mode drought also makes it blind to common-mode noise, and the
noise is an order of magnitude larger.

*What it bought:* an evidence-backed reason to use the cross-ratio, in place of
a conventional one — and the discovery of NCR-14.

### 7. Full senescence limb → an independently-defined drought window

*Date:* 11 October. *Status:* **result not yet confirmed.**

2026's σ⁰VV contrast sits near −5.3 dB through July and August and steps to
about −3.7 dB from 28 August. Testing across the whole 1 July – 30 September
limb averages the drought together with its recovery.

Narrowing the window **because the SAR has a step in it** would be
indefensible. The only legitimate narrowing is one defined by data that knows
nothing about the radar.

Met Éireann soil moisture deficit at Oak Park (station 375) is computed from
rainfall and evapotranspiration. The rule — *longest spell with moderately
drained SMD ≥ 50 mm lasting at least 10 days*, with 50 mm the Irish agronomic
convention for water-limited grassland — was specified before the data was
fetched, and the derived window was written to
`results/phase4/drought_window.json` with its rule and a timestamp **before any
SAR test was run**.

Derived window: **2 July – 28 August 2026, DOY 183–240.**

Two independent observations then coincided:

- SMD fell below 50 mm on **29 August**
- The SAR contrast recovered between the **28 August and 3 September**
  acquisitions

A radar measurement and a rainfall-and-evapotranspiration model, sharing no
input, place the drought break within one 6-day repeat cycle. This is
corroboration that the SAR responds to soil moisture, and is the first positive
finding the project produced.

---

## Superseded results, preserved

Kept because the technical report cannot carry all of them, and because a
re-specification that is not shown alongside what it replaced is not auditable.

**Aggregate, 2026 vs 2025 (§2):** null, detection floor 0.63 dB per acquisition.

**Stratified, three years, 2025 as sole baseline (§3):** six estimates all
negative, 2026 steepest in all three contrasts. *Retracted.*

**Stratified slope test, five-year baseline, full limb (§3, §4):**

| contrast | baseline | τ | 2026 | z | p |
|:---------|---------:|--:|-----:|--:|--:|
| grassland − forest | −0.180 | 0.000 | −0.250 | −1.31 | 0.26 |
| tillage − forest | −0.799 | 0.212 | −0.796 | +0.01 | 0.99 |
| dry − wet grassland | −0.147 | 0.072 | −0.236 | −1.02 | 0.37 |

Detection limit from this configuration: the design resolves an **81%** change
in senescence rate; the drought produced **38%**.

**VV and VH slope tests, full limb (§5):** *superseded by NCR-14, retained as
the evidence for it.* 2024 outlier at z up to −4.75 in all six.

**Level test at day 227, full limb, all three observables (§5, §6):** nine
tests, all negative in sign, none significant. Best p = 0.155.

---

## Current status

**Window-restricted test, cross-ratio, grassland − forest:**

| year | slope (dB/month) | n | r² |
|---:|---:|---:|---:|
| 2021 | −0.282 ± 0.108 | 9 | 0.49 |
| 2022 | −0.211 ± 0.041 | 5 | 0.90 |
| 2023 | −0.071 ± 0.326 | 5 | 0.02 |
| 2024 | −0.150 ± 0.064 | 4 | 0.73 |
| 2025 | −0.107 ± 0.086 | 10 | 0.16 |
| baseline | **−0.188**, τ = 0.000 | | |
| **2026** | **−0.390 ± 0.060** | 10 | **0.84** |

**z = −3.00, p = 0.0398.** Senescence rate roughly doubled. Calibration clean:
every baseline year within |z| ≤ 1.02.

**Supporting:** dry − wet grassland z = −2.57, p = 0.062, same direction.
Narrowing the window sharpened grassland from z = −1.31 to −3.00, which is what
a real signal predicts and noise does not.

**Against:** thirty-six primary tests have been run; 1.8 results under p = 0.05
are expected by chance and this is exactly one. Bonferroni's threshold is
0.0014. **Tillage − forest fails** (z = −0.67, p = 0.54) and its null is
informative rather than underpowered — its detection threshold is 67% of its
baseline slope, so it could have seen a proportional doubling. The coherence
criterion written before the test ran — *grassland and tillage moving together
against forest, with dry grassland moving further than wet* — is met two ways
of three.

**Status: a specific, well-calibrated, physically coherent hypothesis. Not an
established finding.** It requires confirmation on data that did not generate
it. See `REMAINING_WORK.md`.

---

## What the failure pattern says

Sixteen nonconformances (`PROJECT_PLAN.md` §15). **Fifteen are plumbing; one is
method.**

| class | count | NCRs |
|:------|------:|:-----|
| Correct computation, wrong words on top | 7 | 04, 06, 07, 09, 13, 15, 16 |
| Configuration and environment | 5 | 05, 10, 11, 12 |
| Logic | 3 | 01, 02, 03 |
| API that does not do what its name says | 1 | 08 |
| **Method** | **1** | **14** |

The dominant family is a correct calculation presented wrongly — a label, a
unit, a diagnostic that names the wrong cause. Those survive review, because
the code looks right and the number looks plausible. Three of them were
*diagnostics that sent the operator after the wrong thing*: NCR-11 advised
re-running a command that had already succeeded, NCR-15 reported a path typo as
a permissions problem, NCR-16 printed a count under a label describing a
different count.

Every defence that actually worked is a check on plumbing, not on radar:

- checking a printed value against an independently known quantity
  (16 million 10 m pixels **must** be 1,600 km²)
- asserting a patch matched before applying it
- verifying before deleting
- preflighting before downloading
- a tool reporting a by-product it was not asked for (NCR-12 was found by the
  cross-calibration script, which had to align two rasters to compare them)

The single method error, NCR-14, was found the same way: by running an analysis
expected to confirm something else.
