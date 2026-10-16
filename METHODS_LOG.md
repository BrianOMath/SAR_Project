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
it.

*Written 12 October. The confirmation ran on 15 October and refuted it — see
below. This paragraph is left exactly as it stood, because a record of what was
believed before the test is worth more than a tidy one written after.*

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

---

## 14 October 2026 — the batch, and two operational failures

Neither of these is a nonconformance against a requirement: nothing was
measured wrongly and no result changed. They are recorded because both were
diagnosed from a failure *signature* rather than from an error message, and
that reasoning is the transferable part.

### The run stopped at 06:30 with no error

The batch was 35 hours of download-and-process and it stopped overnight,
silently. There was no traceback, no non-zero exit, nothing in the log to say
why.

The diagnosis came from a mismatch between two files that should have been in
step. `batch_process.py` appends to the manifest after a scene verifies, and
writes its progress line to the log before starting the next one. The log was
**one row behind** the manifest. A crash inside the processing of scene *n*
leaves the log ahead — it has announced a scene the manifest never records. A
process killed between the two writes leaves the log behind, which is what was
there.

So the process was terminated from outside, not broken from inside. `powercfg
/requests` confirmed sleep was not the cause, and `powercfg -lastwake` and the
standby timeouts were all zero. The machine had not slept; something had
reaped the process. The manifest-as-state design meant this cost nothing —
`already_done` counts only verified scenes, so the restart resumed at scene
*n* and the 35-hour run completed with zero outstanding failures.

The lesson is about the ordering of two writes, which was not designed for
this and turned out to be a diagnostic. **Write progress before the work and
state after it, and the gap between them tells you which end died.**

### CDSE began refusing mid-run

The visible failure was a `ConnectionResetError` (WinError 10054) followed by
repeated `ConnectTimeoutError` against
`catalogue.dataspace.copernicus.eu`, and two downloads lost outright.

That reads as a network fault, and it is not. **A connect timeout is the TCP
handshake not completing**, which is refusal, not slowness: a congested link
drops packets mid-transfer, a host that will not talk to you fails before the
transfer starts. The two signatures are distinguishable and they call for
opposite responses — retry harder, or stand down.

CDSE limits concurrent downloads per user and monthly transfer volume. This
run used one sequential stream and was far inside both, so the cause was
transient server-side refusal rather than an exhausted quota. Three things
about the downloader were wrong for that:

1. **The backoff gave up in 15 seconds** — three attempts, 5 s then 10 s.
   Throttling clears on a scale of minutes, so the retry policy was sized for
   a dropped packet and the fault was not a dropped packet.
2. **One 120-second timeout covered both connect and read.** Each doomed
   attempt spent two minutes discovering something a refused handshake
   reports in seconds.
3. **A failed job went straight to the next product.** Retrying into an
   active throttle extends it, so one refusal cascaded into a run of
   consecutive failures — which is why two were lost rather than one.

The rebuilt policy separates the two phases and sizes each to its own failure
mode: six attempts at 30 s doubling to 480 s (about fifteen minutes of
patience), a 30-second connect timeout against a 300-second read timeout
because a 1.7 GB product legitimately goes quiet between chunks, and a
fifteen-minute cooldown after a product is abandoned. The five affected
acquisitions were recovered on the next pass.

Two properties of the original design are what made this survivable rather
than fatal: a failed download costs nothing, because the manifest records the
failure and the next run retries it; and the raw product is deleted only
after the output verifies, so a failure never destroys its own input.

---

## 15 October 2026 — the confirmatory test, and NCR-18

Both treatment years were tested against the nine-year baseline fixed on
12 October and amended on 13 and 15 October. Both are refuted. The reason one
of them ever looked significant is the most useful finding the project has
produced.

### 2018 — refuted on direction

Grassland − forest, cross-ratio slope, DOY 182–253, against nine baselines:

| | |
|:--|:--|
| baseline | −0.116 dB/month (between-year sd 0.043, k = 9) |
| 95% prediction interval | [−0.395, +0.163] |
| **2018** | **+0.047 ± 0.109**, z = **+1.35**, p = 0.215 |

The pre-registered rule required 2018 to be *steeper* than baseline **and**
z ≤ −2.306. It is flatter, and the sign is positive. The test fails on
direction before significance is reached, so no power argument applies: the
estimate sits on the wrong side of the baseline, not merely too close to it.

The co-primary level test at DOY 227 disagrees — 2018 sits below baseline in
all three contrasts (grassland − forest z = −2.53, tillage − forest z = −3.27,
dry − wet z = −2.03) and the slopes are flatter in all three. Amendment 1 fixed
in advance that a slope/level disagreement is itself the finding and is not
resolved by preferring the more favourable. It is reported as a disagreement.

Its calibration also fails: on grassland − forest the most extreme *baseline*
year is 2017 at z = +3.37, further from the baseline than 2018.

**A post-hoc hypothesis was raised and deliberately not pursued.** 2018's
drought window opens on DOY 151 and the fit starts at 182, so 31 days of
drought sit outside the fitted range, and "already low, now flat" is what you
would see if senescence had happened before the fit began. That idea arrived
after the result. Amendment 1 excluded DOY 151–181 for a stated reason, before
the data existed, and refitting now would be fitting the test to the answer. If
it is worth pursuing it must be pre-registered and tested on a year not yet
used.

### 2026 — the earlier result does not survive a wider baseline

Same estimate, different comparator:

| baseline set | k | pooled | τ | z | p | |
|:--|---:|---:|---:|---:|---:|:--|
| **9 years (pre-specified)** | 9 | −0.055 | 0.169 | −1.74 | 0.119 | inside |
| 7, dropping 2016 + 2017 | 7 | −0.086 | 0.173 | −1.53 | 0.177 | inside |
| 8, dropping 2020 | 8 | −0.141 | 0.058 | −2.71 | 0.030 | outside |
| 5, the original 2021–2025 | 5 | −0.188 | 0.000 | −2.99 | 0.040 | outside |

2026's slope is **−0.390 ± 0.060 in every row**. Nothing about the treatment
year changed. The earlier z = −3.00, p = 0.0398 and this z = −1.75, p = 0.119
are the same measurement against different baselines.

**The whole result rests on one year.** 2020's grassland − forest slope is
**+0.454 ± 0.112** where most years are negative. Including it raises the
between-year sd from 0.058 to 0.169 and moves the pooled baseline from −0.141
to −0.055; both changes put 2026 inside the interval. The original five-year
baseline was 2021–2025, which excludes 2020. That omission is the entire
difference between p = 0.04 and p = 0.12.

### NCR-18 — τ = 0.000 was read as a strength and was a small-sample artefact

**What was believed.** Zero between-year variance across five years was treated
as evidence of pipeline stability and quoted as a headline figure.

**What is true.** With k = 5, DerSimonian–Laird returns τ² = 0 whenever
within-year sampling error accounts for the observed scatter. The prediction
interval then collapses toward the treatment year's own standard error, and a
tight interval produced by having too few years is indistinguishable from one
produced by a stable measurement. τ = 0.000 from five years is a warning that
the baseline is too small to estimate between-year variance, not a finding
about the instrument.

**The compounding error.** `REMAINING_WORK.md` listed more baseline years under
*explicitly not worth doing*. Quoted in full, because the reasoning is the
point and the file has since been retired:

> **More baseline years for the 2026 full-limb test.** The variance
> decomposition settles it: 82% of the uncertainty is 2026's own fit error and
> 0% is between-year variation, so the detection threshold falls only from
> 0.147 to 0.107 dB/month going from five baseline years to fifteen. T1 adds
> years for a different reason — a second treatment year — not to sharpen 2026.

That decomposition was computed from the same five years that produced the
artefact: it reported 0% between-year variation because the estimator had
truncated to zero, and was then used to argue that more years would not help.
The argument was circular, and nine years break it — between-year sd is 0.169,
three times 2026's own standard error. The same document also stated, under the
same heading, that "the pipeline is validated at τ = 0.000 across five years
and four platforms", which converts the artefact into a validation claim.

The transferable form: **an argument for not collecting more data, built from a
statistic that only the shortage of data produced.**

**Classification.** A method error, the second in the project after NCR-14, and
of the same family: a statistic computed correctly and interpreted as something
it is not.

### NCR-19 — the figure script was pinned to the superseded baseline

Found on 16 October while closing out the repository, by re-running `figures.py`
against the eleven-year series.

*Observed:* the script read all 316 acquisitions, announced "316 acquisitions",
and produced figures identical in every byte but one to the five-year run. Only
the figure that plots raw points changed; the three that compute a baseline
distribution did not.

*Cause:* `TREAT = 2026` and `BASE = [2021…2025]` were module-level constants
with no command-line override. The script silently used five of the eleven
years it had been given, and captioned the result *"2026 against the five-year
baseline distribution"*.

*Why it matters more than it looks:* these figures are what a reader looks at
first. Published as they stood, the report would have argued that a five-year
baseline is an artefact while its own figures displayed one, confidently
labelled, with nothing to indicate disagreement. Nobody comparing the two would
have concluded the figures were stale; they would have concluded the analysis
was inconsistent.

*Fix:* `--treat-year` and `--base-years`, defaulting to the nine pre-registered
baselines; every caption that stated a count now derives it from the data; and
the script refuses to run when the series lacks a requested baseline year
rather than quietly dropping it. The fig-2 caption now also names its fit range,
because it fits the full senescence limb while the report's primary test fits
each year's drought window, and the two give different p-values.

*Classification:* family (b), correct computation presented wrongly — the eighth
occurrence, and the first found after the analysis was believed finished.

*A note on the fix.* The patch asserted each of its seven anchors matched
exactly once and called `ast.parse` on the result, which is the discipline that
had worked all project. It passed, and the file would not run: `global TREAT`
placed after a use of `TREAT` in the same function is a `SyntaxError` raised by
the compiler, not the parser. `ast.parse` builds a tree without resolving
scope. The check is now `compile()`. This is the same shape as the graph-v4
defect — well-formed XML, missing `<operator>` — where a structural check
passed something semantically void. **A validator answers the question it was
built to answer, and the useful question is usually one step further on.**

### The single-baseline trap, fourth occurrence

Identical 2026 data, grassland − forest: **p = 0.0153** against 2025 alone,
**p = 0.119** against the nine-year distribution. Dry − wet: **p = 0.0029**
against 2025 alone, null against nine years. Earlier occurrences: VH tillage
(p = 0.046 → 0.20), the level difference-in-differences against 2025 alone, and
the original 2026 window result.

### Calibration failed in every primary cell

Across both runs, twelve primary cells, each one reports a baseline year
further from the baseline than the treatment year: 2020 at z = +4.50, 2017 at
z = +3.37, 2021 at z = −2.39, 2022 at z = −2.28, 2016 at z = +1.74. The
prediction intervals are not wide enough to call any year unusual. This is the
clearest statement the project can make about its own sensitivity.

### The awkward fact

**2020 had 950 deficit-days — the third most severe drought in the 23-year
record — and the shallowest grassland − forest slope in the series, in the
wrong direction.** Either the measurement is too noisy at this precision for
2020 to mean anything, in which case it is too noisy for 2026 to mean anything
either, or the drought-to-slope relationship is not there. Neither reading
supports the hypothesis.

### What stands

The detection-limit conclusion, and it is now far better supported. Nine
baseline years put ordinary year-to-year variation in the grassland − forest
cross-ratio slope at **±0.17 dB/month**, larger than any drought effect the
record could evidence. The earlier version of this conclusion rested on a
five-year baseline that understated that variation; it is now measured against
eleven years and four satellites.

Also standing: pipeline repeatability, inter-platform agreement (0.171 dB worst
channel, 0.011 dB cross-ratio), slice-assembly agreement (0.0000 and
−0.0011 dB against a 0.171 dB bound), one shared lattice across all 316 scenes,
and a frozen-window discipline that held from first specification to final
test.

### What the project now reports

Not "SAR cannot see drought in Irish grassland" — the measurement was never
sensitive enough to support a claim that strong. The finding is narrower and
transfers further: **a five-year baseline reporting zero between-year variance
produced a result that nine years refute, and the zero was the tell.** Any
difference-in-differences on a short environmental record is exposed to the
same failure.

The pre-registration committed in writing, before the data existed, that either
outcome would be reported with equal prominence. This is the less satisfying
outcome and the more useful one.
