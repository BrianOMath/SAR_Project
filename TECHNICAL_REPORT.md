# Detection limits of Sentinel-1 cross-ratio for drought monitoring over Irish farmland

**A six-year analysis of the 2026 south-east Ireland drought**

Brian Ó Mathúna · 4 October 2026 · rev. 1

---

## Summary

Ireland experienced an unusually prolonged, hot drought in summer 2026. Teagasc's
PastureBase recorded national grass growth of 9,219 kg DM/ha, 412 kg below the
five-year average, with the south-east worst affected. This study asked whether
that impact was visible in Sentinel-1 C-band SAR over a 1,600 km² area of the
Carlow tillage belt.

**It was not.** Across 156 acquisitions spanning 2021–2026 on a single frozen
orbital configuration, no statistically significant drought signal was detected
in any of three stratified contrasts.

The useful result is the arithmetic behind that null. Post-peak senescence rate
in the grassland-versus-forest cross-ratio contrast is **−0.181 dB/month**, and
it is remarkably stable: the between-year standard deviation across five
baseline years and four different satellite combinations is **zero** — all
observed scatter is explained by fitting error alone. Against that stable
baseline, the measurement can resolve a change in senescence rate of **81%**.
The 2026 drought produced **38%**.

The drought was therefore about half the size this method can detect. A variance
decomposition shows the shortfall cannot be closed by additional baseline years
(the detection threshold falls only from 0.147 to 0.107 dB/month going from five
baseline years to fifteen) nor by plausible reductions in residual noise.

A secondary methodological finding emerged with a clearer practical bearing: in
a difference-in-differences design, **a control works by being similar, not by
being inert**. A dry-versus-wet grassland contrast using 49,000 pixels achieved
50% better precision than the whole-area aggregate and twice the precision of a
grassland-versus-forest contrast using 3.9 million.

---

## 1. Objective, and how it changed

The original question was whether SAR could detect drought impact on vegetation
and support an inference about crop yields.

That framing was abandoned early, for a reason worth recording. Yield prediction
was not available: the 2026 harvest was already in by the time analysis began,
and no parcel-level ground truth existed against which a prediction could be
scored. A pre-registered prediction against the CSO's *Area, Yield and
Production of Crops* release (approximately 1 May 2027) was substituted, and the
retrospective component became the primary work.

The question actually answered is narrower and more tractable:

> Given a validated Sentinel-1 processing chain and six years of consistent
> acquisitions, is the 2026 drought distinguishable from ordinary interannual
> variation — and if not, by how much is it missed?

---

## 2. Study area and data

### 2.1 Area of interest

A 40 × 40 km square (1,600 km²) centred on E 673044.2, N 679462.2 in
EPSG:2157 (IRENET95 / Irish Transverse Mercator), covering the Carlow tillage
belt and containing Met Éireann station 375 at Oak Park. The AOI was chosen for
high arable fraction and the presence of a synoptic station.

Land cover composition from the National Land Cover Map 2018 (EPA and Tailte
Éireann), 197,134 polygons intersecting the AOI across 29 Level-2 classes:

| class | km² | % AOI |
|:------|----:|------:|
| Improved Grassland | 737.9 | 46.1 |
| Cultivated Land | 454.2 | 28.4 |
| Coniferous Forest | 56.0 | 3.5 |
| Transitional Forest | 53.7 | 3.4 |
| Hedgerows | 41.2 | 2.6 |
| Wet Grassland | 38.5 | 2.4 |
| Broadleaved Forest and Woodland | 37.9 | 2.4 |
| Mixed Forest | 10.5 | 0.7 |
| Dry Grassland | 17.0 | 1.1 |

### 2.2 Orbital configuration

Phase 0 reconnaissance evaluated all orbit/direction combinations covering the
AOI. **Relative orbit 1, ASCENDING** was selected and frozen for the duration.
It was the only viable candidate: competing orbits 74 and 103 achieved AOI
coverage of 0.371 and 0.178 respectively against orbit 1's 1.000.

The selection also held when the time span was later extended from three years
to six — the configuration was not an artefact of the shorter window.

Orbit 1 further offered an evening overpass (~19:15 local), avoiding morning dew
on the canopy, and required mosaicking on only 2 of 158 acquisitions.

### 2.3 Acquisitions

158 acquisitions, April–October, 2021–2026. 156 processed; 2 excluded under
REQ-17 (multi-slice acquisitions, mosaicking not implemented), neither falling
in the analysis window.

| year | acquisitions | Jul–Sep limb | max gap in limb (d) | platforms |
|-----:|-------------:|-------------:|--------------------:|:----------|
| 2021 | 36 | 15 | 6 | S1A 18 / S1B 18 |
| 2022 | 18 | 8 | 12 | S1A 18 |
| 2023 | 17 | 7 | **24** | S1A 17 |
| 2024 | 16 | 6 | 12 | S1A 16 |
| 2025 | 35 | 15 | 6 | S1A 18 / S1C 17 |
| 2026 | 36 | 15 | 6 | S1A 8 / S1C 14 / S1D 14 |

Products: Sentinel-1 IW GRDH, dual polarisation VV+VH, from the Copernicus Data
Space Ecosystem.

Coverage was essentially perfect: 157 of 158 acquisitions at 1.0000 AOI
coverage, one at 0.9999, minimum edge margin 16.9 km and median 48.8 km.

**Constellation note.** The series spans four platforms. Sentinel-1B operated
until December 2021; Sentinel-1A was terminated on 29 June 2026; Sentinel-1C and
1D entered service in 2025 and 2026. Platforms interleave within seasons rather
than switching once at a handover, which permits same-season inter-platform
comparison (§4.2).

---

## 3. Processing chain

Executed headless via SNAP `gpt` from a version-controlled graph
(`graphs/s1_grd_preprocess_v3.xml`):

```
Read → Apply-Orbit-File → ThermalNoiseRemoval → Remove-GRD-Border-Noise
     → Calibration → Subset → Terrain-Correction → Write
```

Decisions worth stating:

**σ⁰ is stored and averaged in linear power, not dB.** The mean of a logarithm
is not the logarithm of a mean, and the error is systematic. On a scene half
bright and half dim the correct answer is −12.6 dB and the dB-averaged answer is
−15.0 dB — a 2.4 dB bias, in the same direction every time, against a signal
expected at 1–3 dB. Conversion to dB happens once, at presentation.

**Negative values are retained** (`clipNegativeValues=false`). After thermal
noise subtraction the noise-floor estimate is unbiased but noisy, and discarding
the negative tail biases every mean upward — most severely in VH, which is the
channel closest to the noise floor.

**Precise orbits are mandatory** (`continueOnFail=false`). A silently
substituted restituted orbit is exactly the class of quiet degradation this
project's nonconformance log is about.

**Subset precedes terrain correction**, cutting runtime by roughly an order of
magnitude relative to terrain-correcting the full 250 km swath. The subset is
the AOI buffered by ~4 km, because TC resampling consumes edge pixels.

**`alignToStandardGrid=true`.** With the flag off, SNAP takes each output's
origin from that scene's own reprojected footprint, so every acquisition lands
on a slightly different 10 m lattice. Harmless for per-scene statistics; fatal
for a per-pixel time series. See NCR-12.

Output: 10 m pixels, EPSG:2157, bands `Sigma0_VV`, `Sigma0_VH`,
`projectedLocalIncidenceAngle`. Throughput ~48 s per scene; 73 scenes in 281
minutes wall clock, download-bound.

---

## 4. Method

### 4.1 Per-scene verification

Every scene passed an automated gate before entering the archive, checking band
presence, CRS and pixel geometry, AOI containment **against the valid-data mask
rather than the bounding box**, physical plausibility of σ⁰, and linearity. Raw
products were deleted only after verification passed.

All 156 scenes achieved **100.0% AOI coverage** on all three bands.

### 4.2 Inter-platform calibration (REQ-09)

Relative orbit 1 contains two consecutive-day, different-platform pairs:
2026-04-23 S1C / 2026-04-24 S1D, and 2026-06-28 S1A / 2026-06-29 S1C — the
latter being S1A's final pass on this orbit before termination. Both pairs share
S1C, so the two measurements triangulate onto a common reference.

| pair | σ⁰VV | σ⁰VH | cross-ratio |
|:-----|-----:|-----:|------------:|
| S1D − S1C (23/24 Apr) | −0.070 dB | −0.171 dB | −0.101 dB |
| S1A − S1C (28/29 Jun) | +0.147 dB | +0.035 dB | −0.112 dB |

Projected local incidence angle at Oak Park across all four scenes spans
37.62°–37.70° — a total of 0.08°, equivalent to roughly 0.01 dB of purely
geometric variation. Viewing geometry is therefore excluded as an explanation
for the offsets above.

**Largest single-channel offset: 0.171 dB.** Against an expected drought signal
of 1–3 dB, the platforms may be treated as one instrument.

**The cross-ratio is better calibrated than either channel that forms it.** A
gain error common to both polarisations cancels exactly in a ratio. Two
independent pairs — different platform combinations, two months apart, different
weather — agree to **0.011 dB**, against a 0.22 dB spread across individual
channels. Since the drought metric is the cross-ratio, the platform term it
inherits is ~0.1 dB.

*Caveat.* One day of real surface change sits inside every number here; rainfall
between overpasses moves σ⁰ by more than any plausible gain error. These are
working upper bounds, not isolated instrument constants. Their agreement across
two seasons is what makes them credible.

*Sentinel-1B is uncalibrated* against this reference: S1A and S1B flew the same
ground track six days apart, never one, and S1B's failure preceded S1C's launch
by three years. This does not affect the results in §5.4, because platform
calibration cancels identically within a same-image spatial contrast (§4.4).

### 4.3 Land cover stratification

NLCM 2018 polygons were requested from the EPA/Tailte Éireann feature service by
spatial query, in EPSG:2157 natively — no vector reprojection enters the chain —
and rasterised onto the exact grid of a processed scene. The class raster and
all 156 σ⁰ rasters therefore address identical ground, pixel for pixel, with no
resampling anywhere.

**Transitional Forest (53.7 km²) was excluded from the control.** In NLCM terms
it is clearfell and young replanting; a stand mapped transitional in 2018 is
eight years older by 2026 and carries a large systematic trend of its own. It
would have constituted a third of a control group whose purpose is to hold
still.

**Peatland was unavailable.** Raised, blanket and cutover bog plus both heaths
total 1.5 km², under 0.1% of the AOI. Carlow is not bog country; a second
independent control was anticipated and does not exist here.

**Linear features were excluded** — hedgerows (41.2 km²), treelines, ways, rivers
— because at 10 m nearly every pixel straddles a boundary and the class measures
a mixture rather than a cover type.

Final strata, after 2-pixel (20 m) erosion to remove boundary-mixed pixels:

| stratum | raw px | eroded px | kept | km² |
|:--------|-------:|----------:|-----:|----:|
| grassland | 7,379,065 | 3,858,393 | 52.3% | 385.8 |
| tillage | 4,541,745 | 2,995,073 | 65.9% | 299.5 |
| forest (3 classes pooled) | 1,043,917 | 522,450 | 50.0% | 52.2 |
| wet grassland | 384,843 | 105,695 | 27.5% | 10.6 |
| dry grassland | 169,918 | 49,277 | 29.0% | 4.9 |

Erosion cost is substantial because Irish fields are small and hedge-bounded —
197,134 polygons over 1,600 km² is a mean parcel of 0.8 ha.

**Vintage limitation.** The map is 2018; the SAR is 2021–2026. Forest, peat and
water are static over that interval and improved grassland largely persists.
Tillage rotates, so the tillage stratum carries genuine label error that dilutes
toward finding nothing.

### 4.4 Statistical design

The whole-AOI aggregate proved unable to answer the question (§5.2). The
stratified design replaces it with a **difference-in-differences** estimator:

```
effect = (grass − forest)₂₀₂₆ − (grass − forest)baseline
```

The inner subtraction removes weather. A forest and the field beside it receive
the same rain on the same night, are imaged in the same pass by the same
satellite at the same incidence angle through the same atmosphere. Every
nuisance term is common to both and cancels — including platform calibration,
which is why §4.2's S1B gap is immaterial here.

The outer subtraction removes everything permanent. Forest is darker than grass
in VH every day of every year for structural reasons unrelated to 2026.

Three contrasts were used. Grassland−forest and tillage−forest share a control
and are therefore correlated; dry−wet grassland involves no forest and is
independent of both.

**The test is a prediction interval, not a confidence interval.** The question
is not whether 2026 differs from the average normal year but whether 2026 could
*be* a normal year, so the interval must include the genuine spread of normal
years (τ², estimated by DerSimonian–Laird separately from fitting error) plus
2026's own fit error — not merely the uncertainty in where the baseline centre
lies. Baseline years are weighted by precision, since limb sampling ranges from
6 to 15 acquisitions.

**A leave-one-out calibration check** tests each baseline year against the other
four. Those years are normal by assumption, so this measures what |z| a normal
year produces. A test that cannot clear its own null is reported as such.

The primary hypothesis — accelerated post-peak senescence in grassland relative
to forest — was stated before the stratified code was written, following an
exploratory hint in the aggregate series (p = 0.081 after approximately 28
exploratory comparisons, i.e. uninformative). It was then tested once, on a
contrast the exploratory work had not touched.

---

## 5. Results

### 5.1 Pipeline validation

156 of 156 scenes verified. 100.0% AOI coverage on every band of every scene.
All 156 share one pixel lattice: `(EPSG:2157, 10.0, 10.0, 5.0, 5.0)`.

Seasonal phenology is reproduced independently in all six years: cross-ratio
rises to a late-June maximum and declines 1.2–1.5 dB into autumn, consistent
with growth and senescence of grassland and tillage.

### 5.2 Whole-AOI aggregate — null

Day-of-year matched pairs (each 2026 acquisition against the 2025 acquisition
within four days, June–September, 19 pairs), after applying the §4.2 platform
corrections:

| metric | 2026 − 2025 | p |
|:-------|------------:|--:|
| σ⁰VV | −0.080 dB | 0.58 |
| σ⁰VH | −0.045 dB | 0.78 |
| cross-ratio | +0.036 dB | 0.39 |

**The standard deviation of those matched pair differences is 0.63 dB.** With 16
million pixels averaged, speckle is negligible; this is real geophysical
variability, dominated by soil wetness on the morning of each overpass. It sets
a detection floor near 0.4 dB for the aggregate approach.

A block-mean comparison over July–August appeared to show −0.40 dB in VV, but
this did not survive day-matching and is attributable to 2026's acquisitions
falling approximately two days later in a steeply declining part of the season.

### 5.3 Stratified analysis — null

Post-peak senescence slope, 1 July – 30 September, dB per month:

| contrast | 2021 | 2022 | 2023 | 2024 | 2025 | baseline | τ | **2026** | z | p |
|:---------|-----:|-----:|-----:|-----:|-----:|---------:|--:|---------:|--:|--:|
| grassland − forest | −0.212 | −0.190 | −0.023 | −0.183 | −0.120 | −0.181 | **0.000** | **−0.250** | −1.31 | 0.26 |
| tillage − forest | −1.153 | −0.652 | −0.438 | −0.869 | −0.539 | −0.799 | 0.212 | **−0.796** | +0.01 | 0.99 |
| dry − wet grassland | −0.158 | −0.196 | −0.042 | −0.124 | −0.226 | −0.147 | 0.072 | **−0.236** | −1.02 | 0.37 |

All three place 2026 inside the 95% prediction interval for a normal year.

**τ = 0.000 for grassland−forest is the strongest positive result in this
study.** Five independent years, spanning four different platform combinations,
produce senescence slopes that are statistically indistinguishable; every bit of
observed scatter is accounted for by fitting error alone. A pipeline with
drifting calibration, a grid inconsistency or a land-cover misassignment could
not produce that. The baseline is stable; 2026 simply did not move far enough.

**Tillage shows nothing whatever** — 2026 lands at the baseline mean to three
decimal places. Tillage is intrinsically the noisiest contrast (τ = 0.212),
plausibly because harvest timing varies by weeks between years and dominates any
drought term.

**The dry−wet calibration check fails.** 2023 reaches z = +3.07 among years
assumed normal — and 2023 is the year carrying a 24-day gap inside the
senescence limb with r² = 0.24. That contrast's interval is not trustworthy as
constructed.

### 5.4 Sensitivity — the quantitative result

| contrast | 2026 deviation | minimum detectable | ratio | as % of baseline slope |
|:---------|---------------:|-------------------:|------:|:-----------------------|
| grassland − forest | 0.069 dB/mo | 0.147 dB/mo | 0.47 | observed 38%, detectable 81% |
| tillage − forest | 0.003 | 0.844 | 0.00 | 0%, 106% |
| dry − wet grassland | 0.096 | 0.205 | 0.47 | 68%, 146% |

Two of three contrasts land at **47% of the detection threshold**.

Variance decomposition for grassland−forest:

| source | share of total variance |
|:-------|------------------------:|
| 2026's own slope fit error | 82.4% |
| uncertainty in the baseline mean | 17.6% |
| genuine between-year variation (τ²) | 0.0% |

Because the baseline-mean term is small, **additional baseline years barely
help**: the detection threshold falls from 0.147 dB/month with five baseline
years only to 0.107 with fifteen, against an observed effect of 0.069. Reducing
2026's residual scatter by 70% — well beyond what rainfall regression could
plausibly deliver — still leaves the threshold at 0.073.

The conclusion is not that more work would find the signal. It is that this
observable, over this cover, at this cadence, cannot resolve a drought of this
size.

---

## 6. Discussion

### 6.1 A control works by being similar, not by being inert

Precision achieved by each design on the same question:

| design | SE of the slope difference | pixels |
|:-------|---------------------------:|-------:|
| whole-AOI aggregate | 0.064 | 16,000,000 |
| grassland − forest | 0.088 | 3,858,393 + 522,450 |
| tillage − forest | 0.287 | 2,995,073 + 522,450 |
| **dry − wet grassland** | **0.043** | **49,277 + 105,695** |

The dry−wet contrast is **50% more precise than the aggregate and twice as
precise as grassland−forest, on two orders of magnitude fewer pixels**. Pixel
count is not the limiting factor; the correlation between treatment and control
responses is.

Dry and wet grassland respond almost identically to wind, dew, rainfall and
overpass geometry, differing mainly in drainage — so their difference is quiet.
Grass and forest differ in nearly everything, so their difference inherits all
of it. Forest canopy is additionally not a still reference: wind motion and
canopy water change its backscatter independently of the ground.

Introducing the forest control *raised* the effect estimate (−0.116 → −0.159
against 2025) and raised the noise by the same proportion, leaving significance
essentially unchanged.

**Design implication:** when selecting a control stratum for SAR change
detection, maximise the correlation of nuisance response between treatment and
control, not the control's insensitivity to the treatment effect. A slightly
responsive but well-matched control outperforms an unresponsive but poorly
matched one.

### 6.2 The single-baseline trap

An earlier version of this analysis, using 2025 as the sole reference year,
produced six estimates all negative, with 2026 the steepest in all three
contrasts. That pattern did not survive the addition of 2021–2023.

| contrast | vs 2025 alone | vs 5-year baseline |
|:---------|--------------:|-------------------:|
| tillage − forest | −0.396 dB/mo | +0.003 dB/mo |
| grassland − forest | −0.158 | −0.069 |

The cause is visible in §5.3: **2025 was among the shallowest baseline years
available** in both forest contrasts. Comparing against it alone inflated the
apparent 2026 effect — through no error of method, simply an unlucky reference.

This is a failure mode a single-baseline design cannot detect from within
itself. It is the clearest practical argument in this study for characterising
the baseline distribution rather than selecting a baseline year.

### 6.3 Why the drought was not visible

Teagasc's measurement is of dry matter production — biomass accumulated over a
season. The SAR cross-ratio responds to canopy structure at the moment of
overpass. A sward under water stress grows less but need not become
structurally different enough, at 5.4 cm wavelength, to move volume scattering
by a resolvable amount — particularly when grazing and cutting impose far larger
structural changes on the same fields.

The aggregate result adds a second reason: the per-overpass soil-moisture term
(0.63 dB) exceeds any plausible seasonal drought term, and while the stratified
contrast removes most of it, what remains still dominates.

---

## 7. Limitations

1. **Two of five baseline years are thinly sampled.** 2023 and 2024 carry 7 and
   6 limb acquisitions; 2023's 24-day gap falls inside the senescence limb.
   Precision weighting mitigates but does not remove this.
2. **The dry−wet contrast's interval is not calibrated** (2023 at z = +3.07). A
   sensitivity re-run excluding 2023 is legitimate if reported alongside the
   full result, never instead of it.
3. **The level difference-in-differences was not upgraded** to the multi-baseline
   test and still compares against 2025 alone. Given §6.2, its apparent
   significance for dry−wet grassland (p = 0.0087) should be regarded as
   inflated and is not relied upon here.
4. **Land cover is 2018**; tillage parcels rotate.
5. **Sentinel-1B is uncalibrated** against the S1A/S1C/S1D reference. Immaterial
   to the contrasts, material to the absolute series in §5.2 for 2021.
6. **No ancillary meteorological data** was incorporated. Met Éireann soil
   moisture deficit for Oak Park would convert a correlational result into a
   mechanistic one and was not obtained within scope.
7. **Single AOI, single orbit.** Generalisation beyond south-east Irish mixed
   farmland is not supported by this evidence.

---

## 8. Conclusions

1. The 2026 drought, agronomically significant by independent measurement, was
   **not detectable** in Sentinel-1 cross-ratio over this AOI by any of three
   stratified contrasts.
2. The limitation is quantified: the method resolves an **81% change in
   senescence rate**; the drought produced **38%**.
3. The limitation is **not addressable by more data of the same kind**. Variance
   decomposition shows 82% of the uncertainty arising from the drought year's
   own residual scatter, with between-year baseline variation at zero.
4. Baseline senescence rate is **highly stable** (τ = 0.000 across five years and
   four platforms), validating the processing chain and establishing that the
   null is a sensitivity limit rather than a noise floor in the pipeline.
5. Inter-platform radiometric consistency across S1A, S1C and S1D is **0.171 dB
   worst case per channel and 0.011 dB in the cross-ratio**, permitting the
   constellation to be treated as a single instrument for this purpose.
6. In difference-in-differences SAR designs, **control similarity dominates
   control inertness** as a determinant of precision — demonstrated at a factor
   of two.

### Recommended future work

- Met Éireann soil moisture deficit for Oak Park, to test whether contrast
  evolution tracks SMD within 2026 alone. This is the only remaining step that
  could convert the result from correlational to mechanistic.
- A drainage-stratified grassland control, following §6.1 — same crop, same
  management, differing water-holding capacity.
- Sentinel-2 NDVI over identical strata, as a cross-sensor sensitivity
  comparison. If optical resolves what SAR cannot, the detection-limit result
  gains a direct point of reference.

---

## 9. Engineering record

**Thirteen nonconformances** were raised and closed. **Not one was an algorithm
error.** Classified by root cause:

| class | NCRs | character |
|:------|:-----|:----------|
| Correct computation, wrong presentation | 04, 06, 07, 09, 13 | labelling, unit and diagnostic errors on arithmetic that was already right |
| Configuration and environment | 05, 10, 11, 12 | a GUI default, a missing preflight, a stale manifest, a flag left false |
| Unasserted batched edits | 02, 03 | patches that silently matched nothing |
| A standard-library method that does not do what its name says | 08 | `rstrip` is not `removesuffix` |

Two are worth singling out.

**NCR-12** (`alignToStandardGrid=false`) was invisible to every per-scene check
and to a passing test suite, because it only manifests when scenes are stacked.
It was found by a tool written to measure something else: the cross-calibration
script had to align two rasters to compare them and reported the misalignment as
a by-product. Had it gone undetected, 156 acquisitions would have required
resampling onto a common lattice, degrading σ⁰ 156 times to recover something
that was free at processing time.

**NCR-11** (stale `requirements.txt`) produced a diagnostic that recommended the
exact command the user had already run successfully twice. A diagnostic that can
only suggest one action will suggest it when it is wrong.

**The pattern:** the failure mode of this project was never the physics. It was
configuration, packaging, labelling and environment. Every defence that actually
worked — checking a printed number against an independently known quantity,
asserting a patch matched before applying it, verifying before deleting,
preflighting before downloading — is a check on plumbing, not on radar.

264 automated tests; CI on Python 3.11 and 3.13.

---

## 10. Reproducibility

| artefact | path |
|:---------|:-----|
| Processing graph | `graphs/s1_grd_preprocess_v3.xml` |
| Acquisition catalogue | `S1_Recon/recon_out/scenes.csv`, `acquisitions.csv` |
| Reconnaissance | `S1_Recon/s1_recon.py` |
| Per-scene verification | `S1_Recon/verify_scene.py` |
| Batch runner | `S1_Recon/batch_process.py` |
| Cross-calibration | `S1_Recon/crosscal.py` |
| Time series | `S1_Recon/build_series.py` |
| Land cover | `S1_Recon/fetch_landcover.py` |
| Stratified analysis | `S1_Recon/stratify.py` |
| Results | `results/phase0/`, `phase1/`, `phase2/`, `phase3/` |
| Plan and nonconformance log | `PROJECT_PLAN.md` |

Raw Sentinel-1 products are not committed (REQ-16); the product manifest is,
and is sufficient to re-derive the archive. The catalogue is retained in version
history because the CDSE catalogue is not static — between the first
reconnaissance on 8 September 2026 and the second on 3 October, three new 2026
acquisitions appeared on this orbit.

**Data sources.** Copernicus Sentinel-1 data 2021–2026, processed by ESA,
retrieved from the Copernicus Data Space Ecosystem. National Land Cover Map of
Ireland 2018 © Tailte Éireann and the Environmental Protection Agency, CC BY 4.0.
Grass production figures from Teagasc PastureBase Ireland.

---

*Processing performed with ESA SNAP. Analysis in Python (rasterio, pyproj,
shapely, numpy, scipy).*
