# SAR-Bog: Radar signatures of the 2026 Irish drought

**Project plan — Tier A (minimum viable scope)**
Brian Ó Mathúna · drafted 7 September 2026 · rev. 4, 26 September 2026
**Phase 0 complete. Phase 1 complete: pipeline verified end to end, cross-calibration measured, REQ-09 closed (§5). Batch pending graph v3 reprocess (NCR-12).**

Working title for the repo and report:
*Sentinel-1 backscatter anomaly and post-drought recovery over the Carlow tillage belt, summer 2026*

---

## 1. Purpose

To convert the theory from EO College's *Echoes in Space* into a self-directed, publicly verifiable SAR analysis with a real result, built and documented to the same standard as the B-Raspi ground station.

Secondary purpose, equally important: to produce a third instance of the predicted-versus-measured loop that is already the strongest pattern in the portfolio — after the B-Raspi link budget and the COMSOL nanobelt simulation. This project registers a dated, falsifiable prediction *before* the outcome data is published, then verifies it. That is the part that makes it engineering rather than a tutorial repeat.

---

## 2. Background: the 2026 drought

Established facts, from Met Éireann's Climate Statement for Summer 2026:

| Fact | Value |
|:----------------------------------------------|:---------------------------------------------------------------|
| National summer mean temperature | 16.28 °C — hottest on record, 0.09 °C above the 2025 record |
| National summer rainfall | 78% of the 1991–2020 long-term average |
| Absolute droughts (15+ consecutive dry days) | 20 stations, Midlands / South / East, 15–27 days between 1–28 July |
| Longest partial drought on record | Oak Park, Co. Carlow — 20 June to 24 August (66 days) |
| Oak Park summer rainfall | 138.5 mm, 73% of LTA |
| Oak Park summer mean temperature | 17.2 °C — hottest station in the country |
| Highest temperature | 32.2 °C, Athenry, 25 June |
| Drought break | Pattern change to low pressure, widespread rain from late August |
| Northwest (unaffected) | Belmullet 106% of LTA; Newport 98% of LTA |

The agricultural consequence was a fodder crisis in the east and south: Teagasc issued fodder-budget warnings, farm organisations met the Minister in mid-August, and feed shortages were reported specifically in the east and south.

**Why this matters for the project design:** the impact was strongly regional, and the northwest was essentially unaffected. That gives a natural control region — see §13, growth path.

---

## 3. Why SAR, honestly

The case *for*:

- Ireland is one of the cloudiest agricultural regions in Europe. Optical time series over Irish farmland are chronically gappy. C-band SAR is cloud-independent, which is the actual operational argument for radar here.
- Sentinel-1 dual-pol (VV+VH) at 6-day revisit gives a dense, evenly sampled time series across the whole drought and recovery.
- Backscatter responds to both soil moisture and vegetation water content and structure — the two things a drought changes.

The case *against*, stated up front because the report must state it:

- **C-band σ° is confounded.** A fall in backscatter can be dry soil, reduced biomass, or early senescence. SAR alone cannot separate them. This is the central methodological problem of the project, not a footnote.
- **Phenology masquerades as drought.** Cereals senesce and are harvested in July–August anyway. A backscatter drop over a barley field in late July is expected in a normal year. Only the comparison against a baseline year, over the same fields, separates the two.

The design responses to both are in §7 and §8: dual-polarisation ratios that partially suppress the soil-moisture term, a land-cover split, a baseline year, and an independent soil-moisture-deficit series to regress against.

---

## 4. Reframing the crop-yield question

The original idea was to predict a crop-yield impact a few months out. Two problems, and a fix.

**Problem 1 — the harvest already happened.** The Irish cereal harvest runs roughly July to August. As of early September 2026 the winter and spring cereal harvest is in. There is no 2026 yield left to forecast; it is a hindcast.

**Problem 2 — yield forecasting needs a calibrated model and parcel-level ground truth.** Neither is available to a solo project. Field-level yield data is not public; CSO figures are national and annual and arrive well after harvest. Any "yield model" built here would be a correlation against a handful of aggregate numbers, which is not a defensible claim and would be spotted as such in an interview.

**The fix — split it into a hindcast and a genuine forecast.**

- **Hindcast (the bulk of the work):** map and quantify the drought's radar signature through summer 2026 against a baseline year, split by land cover, and regress it against measured soil moisture deficit. This is a real, defensible result.
- **Forecast (small, but the CV-critical part):** the thing that is *still ahead* in September 2026 is autumn sward regrowth and the winter fodder position. Derive a post-drought recovery index from the late-August-onward Sentinel-1 series, use it to make one dated, written-down, falsifiable prediction, commit it to git before the outcome is published, and verify it when Teagasc's winter fodder survey and the CSO crop figures land.

That converts "guess at crop yields" — which would not survive scrutiny — into a pre-registered prediction with a verification date. It is a smaller claim and a much stronger one.

---

## 5. Data configuration and measured performance (locked)

Phase 0 ran on 7–8 September 2026 (`s1_recon.py`, CDSE OData catalogue): 499 products over the AOI for April–October of 2024, 2025 and 2026, merged to 415 acquisitions across five relative orbits.

### Selected configuration

| Parameter | Value |
|:-----------------------------|:------------------------------------------------|
| Relative orbit | **1** |
| Pass direction | **ASCENDING** |
| Overpass | ~18:13–18:14 UTC (~19:15 local) |
| Product | `IW_GRDH_1S`, VV+VH, SAFE container |
| Drought season | 2026 — 31 acquisitions |
| Primary baseline season | 2025 — 35 acquisitions |
| Secondary baseline | 2024 — 16 acquisitions, S1A only, 12-day repeat |
| Volume, 2025 + 2026 | ~118 GB |
| Volume including 2024 | ~146 GB |

### The candidates

| Orbit | Dir | Coverage | Mosaicking needed | Volume | Local overpass | Max gap 2025 / 2026 |
|:---|:---|:---|:---|:---|:---|:---|
| **1** | ASC | 0.9999 | **1 of 82 (1.2%)** | 146 GB | ~19:15 | 12 d / 7 d |
| 23 | DESC | 0.9997 | 40 of 82 (49%) | 217 GB | ~07:47 | 6 d / 11 d |
| 125 | DESC | 0.9998 | 43 of 85 (51%) | 226 GB | ~07:40 | 12 d / 7 d |
| 74 | ASC | 0.371 | — | — | — | rejected: AOI on swath edge |
| 103 | ASC | 0.178 | — | — | — | rejected: AOI on swath edge |

### Why orbit 1 ascending

- **It effectively never needs mosaicking** — 1 acquisition in 82, against roughly half for both descending candidates. Fewer products, ~80 GB less to move, and no seam through the AOI.
- **Evening overpass.** The descending candidates pass at ~07:40 local, peak dew on Irish grassland in summer. Dew raises C-band backscatter; in a study whose entire signal is drying, a morning series is biased in the direction being measured.
- **Largest margin from the swath edge.**
- **Its one weak number is a mirage.** The 24-day maximum gap that made the automatic ranking prefer orbit 125 falls entirely within 2024 — the demoted year. Restricted to 2025–26 the worst gap is 12 days, and through the drought window (20 June – 24 August 2026) orbit 1 delivers **13 acquisitions with a 6-day maximum gap**.

The tool's own ranking recommended orbit 125. It sorts on coverage, year completeness, gap and edge margin, and knows nothing about mosaicking cost, overpass time, or the baseline-year decision. Recorded here because the override was a judgement call, not a bug.

### Baseline decision

**2025 is the primary baseline.** It carries 35 acquisitions to 2024's 16 and matches 2026's sampling density far more closely. 2024 is retained as a secondary check only: S1A alone on a 12-day repeat with a 24-day hole in July.

The limitation flagged at rev. 1 stands and must be stated in the report: summer 2025 was itself the previous hottest on record, so a 2026 anomaly measured against it is **conservative** — the true departure from a long-term norm is larger than what this study will report.

### Platform composition

Orbit 1 carries 42 S1A, 28 S1C and 12 S1D acquisitions. Crucially they **interleave within seasons** rather than switching once at the S1A termination — S1A and S1C alternate on a 6-day offset through 2025 and into June 2026, and the 2026 drought window is 6 × S1C, 6 × S1D, 1 × S1A. This changes REQ-09 from a hard before/after comparison into a paired same-season one.

The `min_edge_dist_km` per platform on the same orbit is not identical — S1A 48.8 km, S1D 60.5 km, S1C 16.9–60.5 km. Same track, slightly different footprints, so the platforms are not geometrically interchangeable and the cross-calibration is not optional.

### First scene verified — 2026-07-17, S1D

The SNAP GPT chain was built, corrected and run end-to-end on one mid-drought scene, then checked with `verify_scene.py`. All hard checks pass.

| Measure | Value |
|:-------------------------------------|:-----------------------------------------|
| Output grid | 6536 × 6763 px, 10 m, EPSG:2157, north-up |
| AOI coverage, all three bands | **100%** — the 4 km subset buffer survives the ~30° rotation |
| Valid data, whole scene | σ° 53.6%, incidence angle 72.2% |
| σ°VV over the AOI | median −13.13 dB (p05 −17.77, p95 −7.17) |
| σ°VH over the AOI | median −18.98 dB (p05 −25.31, p95 −13.15) |
| Cross-ratio VH − VV | **−5.85 dB** — textbook for a vegetated surface |
| Negative VH after noise removal | 16,757 px, 0.10% |
| Incidence angle at Oak Park | **37.67°** |
| Incidence across the AOI | 33.36–43.81°, median 38.60°, p05–p95 spread **10.45°** |

σ°VV at −13.1 dB is at the low end for Irish grassland. That is consistent with a dried surface, but it is a hypothesis until the 2025 baseline exists — do not report it as a drought signal on one scene.

**The incidence spread is the finding that changes the analysis.** 10.45° across the AOI is roughly 1.6 dB of purely geometric backscatter variation. Between dates on orbit 1 it cancels exactly, so the anomaly is safe. Between land-cover classes it may not: the incidence gradient runs across-track while Carlow's tillage concentrates in the north–south Barrow valley, so grassland and arable may sit on systematically different parts of the gradient. That would look exactly like a land-cover difference. See REQ-19.

### Measured throughput

**48 seconds per scene** on the current desktop, subset-before-terrain-correction as designed. A faster machine is expected later, so treat these as an upper bound.

| Set | Scenes | Processing | Volume | Download @100 Mbit |
|:-----------------|-------:|-----------:|-------:|-------------------:|
| 2025 + 2026 | 66 | 53 min | 117 GB | ~2.6 h |
| plus 2024 | 82 | 66 min | 145 GB | ~3.2 h |

Three consequences, all recorded because they change earlier decisions:

- **Phase 2 is an evening, not three days.** Compute is no longer a constraint of any kind; download bandwidth is the only one, and it is domestic broadband rather than a CDSE limit.
- **Add 2024 after all.** It costs 13 minutes of processing and 28 GB. The sampling objection stands — 16 acquisitions on a 12-day repeat is a weak baseline — so 2025 remains primary, but 2024 is now effectively free as a secondary check against interannual noise.
- **Disk risk is gone.** With download → process → delete streaming at 48 s a scene, peak disk is a few raw products, under 10 GB rather than 145. See R3.

### Cross-calibration pairs — the REQ-09 design

The dataset contains two **consecutive-day platform pairs** on orbit 1. One day apart, same track, same geometry: surface conditions are as close to identical as nature allows, so any σ° difference over invariant targets is instrument, not ground.

| Pair | Date | Platform | Product |
|:-----|:-----|:---------|:--------|
| A | 2026-06-28 | S1A | `S1A_IW_GRDH_1SDV_20260628T181435_..._065173_083734_B4D0` |
| A | 2026-06-29 | S1C | `S1C_IW_GRDH_1SDV_20260629T181348_..._008324_010780_297B` |
| B | 2026-04-23 | S1C | `S1C_IW_GRDH_1SDV_20260423T181347_..._007347_00EE71_7EB8` |
| B | 2026-04-24 | S1D | `S1D_IW_GRDH_1SDV_20260424T181357_..._002492_0041C9_702F` |

Pair A is S1A's **last pass on this orbit** before termination on 29 June — the cross-calibration is possible only on the final day it could have been. Four scenes, ~7 GB, four minutes of processing.

Run this before the bulk batch, not after: if there is an inter-platform offset, it is far cheaper to find while the pipeline is still one command.

### Cross-calibration measured — REQ-09 closed

Both pairs processed 20 September 2026 and measured 26 September, over 16.0 M
AOI pixels each. Offsets are AOI-mean linear σ⁰ ratios expressed in dB, with the
negative tail retained (clipping is off by design, and discarding it would bias
every mean upward). Both pairs share S1C, so the two measurements triangulate
onto a common reference.

| Pair | Comparison | σ⁰VV | σ⁰VH | cross-ratio (VH−VV) |
|:-----|:-----------|-----:|-----:|--------------------:|
| B | S1D − S1C, 23/24 Apr | −0.070 dB | −0.171 dB | −0.101 dB |
| A | S1A − S1C, 28/29 Jun | +0.147 dB | +0.035 dB | −0.112 dB |

**Geometry is not a factor.** Projected local incidence angle at Oak Park is
37.70°, 37.70°, 37.62° and 37.66° for the four scenes, and 37.67° for the
17 July S1D scene — a total spread of 0.08° across three platforms and four
months. At ~0.1–0.15 dB per degree over vegetation that is ~0.01 dB, two orders
of magnitude below the offsets above. Whatever those offsets are, they are not
viewing geometry.

**The largest single-channel offset is 0.171 dB** (σ⁰VH, pair B), against an
expected drought signal of 1–3 dB in the cross-ratio. The platforms may be
treated as one instrument.

**The cross-ratio is better calibrated than either channel, and this is the
substantive finding.** A gain error common to both polarisations cancels exactly
in a ratio. The two pairs — different platform combinations, two months apart,
different weather — give cross-ratio offsets of −0.101 dB and −0.112 dB, in
agreement to **0.011 dB**. Two independent measurements agreeing that closely
are not each other's coincidence. Since the drought metric is the cross-ratio,
the platform term it inherits is ~0.1 dB, roughly 20× smaller than the 0.22 dB
spread across individual channels. Carried explicitly in the analysis rather
than corrected.

**Caveat, stated for the record.** One day of real surface change sits inside
every number here; rain between two overpasses moves σ⁰ by more than any
plausible gain error. These are therefore working upper bounds on the platform
term, not isolated instrument constants. The agreement between two pairs in
different seasons is what makes them credible — a weather artefact would have
to repeat itself in April and June to survive that test.

*Angle stratification.* Offsets were binned in 2° incidence bands to confirm no
geometric residual. All four channel/pair combinations are flat to ≤0.18 dB. The
pair-A σ⁰VV bins rise across three bands then drop in the 40–42° tail — scatter
in a thin, land-cover-skewed sample, not a slope. See NCR-13.

---

## 6. Objectives and hypotheses

**O1.** Build a reproducible, headless Sentinel-1 GRD processing chain from raw product to analysis-ready calibrated, terrain-corrected backscatter over a fixed area of interest.

**O2.** Produce σ°VV, σ°VH, cross-ratio and RVI time series for the 2026 growing season and the 2025 baseline season, stratified by grassland and arable land cover.

**O3.** Quantify the 2026 anomaly against the baseline and test it against Met Éireann's measured soil moisture deficit at the same location.

**O4.** Derive a post-drought recovery index and register one falsifiable forward prediction.

**O5.** Document the whole thing to B-Raspi standard: requirements, verification matrix, nonconformances, technical report, CI-tested code.

### Hypotheses

These are written to be falsifiable. A disproved hypothesis is a result, and — as the B-Raspi calibration work already demonstrates — disproving your own expectation reads better than confirming it.

- **H1.** σ°VV falls earlier and more steeply than the cross-ratio during the drying phase, because VV carries more of the soil-moisture signal and the cross-ratio partially suppresses it.
- **H2.** The 2026 minus baseline anomaly in cross-ratio and RVI is larger over grassland than over arable land during July, because arable backscatter is already dominated by normal senescence and harvest. *If H2 fails, the interesting question becomes why — and that is a better discussion section than a confirmation.*
- **H3.** σ°VV over grassland correlates negatively with Met Éireann's Oak Park soil moisture deficit, with the correlation strongest for the well-drained soil class.
- **H4.** Recovery in the vegetation indices after the late-August rain is measurable within three to four revisit cycles, and is slower over ground that showed the deepest July anomaly.

---

## 7. Requirements

Written in the same style as the B-Raspi requirements set. Verification methods: **T** test, **A** analysis, **I** inspection, **D** demonstration.

| ID | Requirement | Method |
|:---------|:---------------------------------------------------------------------------|:---------|
| REQ-01 | The AOI shall be a fixed polygon of approximately 40 × 40 km centred on Oak Park, Co. Carlow, and shall not change once processing begins. | I |
| REQ-02 | All acquisitions shall come from Sentinel-1 **relative orbit 1, ascending**. No other orbit or pass direction enters the analysis. This configuration is frozen by §5; any change is raised as a nonconformance. | T |
| REQ-03 | The analysis shall cover April to October inclusive for the 2026 drought season and the 2025 primary baseline season. 2024 may be processed as a secondary check but shall not serve as the reference baseline. | I |
| REQ-04 | The processing chain shall run headless and unattended from a single command over a list of input products. | D |
| REQ-05 | The chain shall apply, in order: precise or restituted orbit file, thermal noise removal, GRD border noise removal, radiometric calibration to σ° in linear power, AOI subset, and Range-Doppler terrain correction to EPSG:2157 at 10 m. | I |
| REQ-06 | Backscatter shall be stored and spatially averaged in **linear power**, and converted to dB only for presentation. | T |
| REQ-07 | Per-date, per-class statistics shall be aggregated over a minimum of 1000 pixels per land-cover class to suppress speckle, and the effective number of looks shall be recorded. | T |
| REQ-08 | Land-cover stratification shall use the National Land Cover Map of Ireland 2018 (EPA / Tailte Éireann), reduced to a grassland class and an arable class, with a boundary buffer applied to exclude mixed pixels. | I |
| REQ-09 | The pipeline shall demonstrate radiometric consistency between Sentinel-1A, 1C and 1D over pseudo-invariant targets within the AOI, and shall report the measured inter-platform offset in dB per polarisation. Because the platforms interleave on relative orbit 1, comparisons shall be made between platforms within a window short enough for surface conditions to be stable (nominally ≤14 days), not across the 29 June 2026 termination date. | T |
| REQ-10 | Any residual step change that cannot be corrected shall be recorded as a documented nonconformance rather than silently absorbed. | I |
| REQ-11 | Independent meteorological data — daily rainfall, temperature and soil moisture deficit for Oak Park — shall be ingested from Met Éireann and time-aligned to the SAR acquisition dates. | T |
| REQ-12 | Acquisition dates within 24 hours of a recorded rainfall event shall be flagged, so that wet-canopy and wet-surface contamination can be excluded or discussed. | T |
| REQ-13 | The analysis code shall have an automated test suite run in CI on every push, covering the numerical core and the date/orbit selection logic. | T |
| REQ-14 | One forward prediction shall be recorded in the repository, with its verification criterion and verification date, and committed before the corresponding outcome data is published. | I |
| REQ-15 | The project shall produce a technical report structured as abstract, methods, results, discussion, with every figure reproducible from the committed code and data manifest. | D |
| REQ-16 | Raw Sentinel-1 products shall not be committed to the repository; a manifest of product identifiers sufficient to re-download them shall be committed instead. | I |
| REQ-17 | Any acquisition arriving as more than one GRD slice shall be mosaicked before subsetting. Any acquisition whose slices are non-contiguous shall be excluded from the time series and the exclusion recorded. | T |
| REQ-18 | Coverage, gap and completeness metrics shall be computed per acquisition (slices merged) and on calendar dates, never per product or on elapsed timedeltas. Spatial checks shall test the AOI against the valid-data mask, not the raster bounding box. | T |
| REQ-19 | The incidence-angle distribution shall be computed per land-cover class. If the grassland and arable distributions differ materially, class comparisons shall be made within matched incidence bands rather than pooled, and the decision recorded. | A |

---

## 8. Study area, data and method

### 8.1 Area of interest

A ~40 × 40 km box centred on Teagasc Oak Park, Co. Carlow (approx. 52.86 °N, 6.92 °W).

Chosen because it uniquely stacks four things in one footprint:

1. The **driest and hottest** synoptic station in the country in summer 2026, and the longest partial drought on record.
2. A **Met Éireann synoptic station** on site, publishing daily rainfall, temperature and soil moisture deficit — free, open, and exactly the independent variable the analysis needs.
3. **Teagasc's national crops research centre**, so the agronomic context for the season is documented publicly.
4. A genuine **mix of tillage and grassland** in the Barrow valley, giving two contrasting land-cover responses inside one AOI at no extra processing cost.

Terrain is gentle, which keeps terrain correction straightforward and makes σ° acceptable without full radiometric terrain flattening.

### 8.2 Data

| Dataset | Source | Use |
|:-------------------------------------------|:-------------------------------|:------------------------------|
| Sentinel-1 IW GRDH, VV+VH | Copernicus Data Space Ecosystem | Primary observable |
| Copernicus DEM 30 m | Auto-downloaded by SNAP | Terrain correction |
| National Land Cover Map 2018 | EPA / Tailte Éireann, data.gov.ie | Grassland / arable stratification |
| Oak Park daily climate data | Met Éireann via data.gov.ie | Rainfall, temperature |
| Daily soil moisture deficit, by soil drainage class | Met Éireann agri-meteorological data | Independent moisture variable for H3 |
| Teagasc Grass10 weekly growth rates | Teagasc, regional aggregates | Qualitative grassland ground truth |
| Teagasc 2026 drought impact report; CSO crop yields | Teagasc, CSO | Outcome data for the prediction verification |

### 8.3 Baseline year — settled

See §5. 2025 is the primary baseline (35 acquisitions), 2026 the drought season (31), 2024 a secondary check only (16, S1A alone on a 12-day repeat).

The caution raised at rev. 1 stands: summer 2025 was itself the previous hottest on record, so measuring 2026 against it **understates** the departure from a long-term norm. This is a stated limitation, not a flaw — the report must give the direction of the bias, and any headline anomaly figure should be described as conservative.

### 8.4 Processing chain

Built once in SNAP Desktop as a graph, then exported to XML and run headless with `gpt` over the full scene list from bash, containerised for reproducibility.

```
Read
  → Apply-Orbit-File          (precise, fall back to restituted)
  → ThermalNoiseRemoval       (VV, VH)
  → Remove-GRD-Border-Noise
  → Calibration               (output σ°, linear power, not dB)
  → Subset                    (geoRegion = AOI polygon)
  → Terrain-Correction        (Range-Doppler, Copernicus 30 m DEM,
                               bilinear, 10 m, EPSG:2157)
  → Write                     (GeoTIFF, linear power)
```

Deliberate choices worth defending in the report:

- **Subset early.** Immediately after calibration, before terrain correction — cuts runtime by roughly an order of magnitude versus terrain-correcting the full 250 km swath.
- **No speckle filter.** Spatial filtering biases the statistics and is unnecessary when aggregating thousands of pixels per class per date. Speckle averages out with sample size; a Refined Lee filter would only blur class boundaries. Record the effective number of looks instead (REQ-07).
- **Linear power throughout, dB only at the plot.** Averaging in dB gives the wrong mean — a classic and quietly damaging error. REQ-06 exists specifically to make this testable.
- **EPSG:2157** (IRENET95 Irish Transverse Mercator) so the raster co-registers cleanly with the national land cover map without reprojecting the vector data.

### 8.5 Derived observables

Computed in linear power, per date, per land-cover class:

| Observable | Definition | Interpretation |
|:---------------|:-----------------------------------------------|:----------------------------------------------|
| σ°VV | — | Soil-moisture-weighted; falls as the surface dries |
| σ°VH | — | Volume scattering; canopy structure and water content |
| Cross-ratio, CR | σ°VH / σ°VV (a difference in dB) | Vegetation proxy with the soil-moisture term partially suppressed |
| RVI | 4 σ°VH / (σ°VV + σ°VH) | Vegetation density proxy, bounded |
| Anomaly | 2026 value minus baseline value, same date-of-year window, same class | The actual drought signal |
| Recovery index | Slope of CR from the drought break (24 August) forward | Feeds the forward prediction (O4) |

### 8.6 Analysis

1. Plot the four observables against day-of-year, 2026 versus baseline, grassland versus arable, with the drought window and the break date marked.
2. Test H1 by comparing the date and gradient of the onset of decline in σ°VV against CR.
3. Test H2 by comparing the July anomaly magnitude between land-cover classes.
4. Test H3 by regressing σ°VV against Met Éireann soil moisture deficit, per soil drainage class, with rain-contaminated dates flagged per REQ-12.
5. Test H4 by fitting the post-break recovery slope and checking it against the depth of the July anomaly.
6. Produce a per-pixel anomaly map for the peak drought window — the one figure a non-specialist will actually look at.

---

## 9. Verification approach

A verification matrix in the B-Raspi format, one row per requirement, with the method, the procedure, the evidence artefact and the result. Everything in REQ-02, 06, 07, 09, 11, 12, 13, 17 and 18 is verified by automated test, which continues the V&V upgrade already noted in the experience bank: verification by test rather than by demonstration wherever it can be afforded.

Three verification items carry disproportionate weight and should be designed first:

- **The inter-platform consistency check (REQ-09).** Select stable, temporally invariant targets inside the AOI — a large conifer block, an urban or industrial surface. Phase 0 showed the platforms *interleave* on orbit 1 rather than switching once, so compare S1A against S1C against S1D within short windows where surface conditions are effectively constant, rather than either side of the 29 June 2026 termination. A 2025 fortnight typically holds one S1A and one S1C pass six days apart; the 2026 drought window alternates S1C and S1D. Report the offset in dB per polarisation with a confidence interval. Within the sensor's specified radiometric stability: say so and move on. Outside it: document a nonconformance and carry the offset explicitly. Either outcome is a result — and this design is materially stronger than the before/after comparison assumed at rev. 1. **Closed 26 September 2026** by the two consecutive-day pairs: largest single-channel offset 0.171 dB, cross-ratio offset −0.101 and −0.112 dB from two independent pairs. See §5.
- **The linear-versus-dB averaging test (REQ-06).** A unit test that averages a known set of values both ways and asserts the pipeline uses the linear route. Cheap to write, and it pins a mistake that is invisible once made.
- **The per-acquisition metric tests (REQ-18).** Two tests already in the Phase 0 suite that must carry forward: one asserting that two slices which individually clip the AOI union to full coverage, and one asserting gaps are counted on calendar dates rather than elapsed timedeltas. Both pin real defects — see §15.
- **A synthetic-input end-to-end test.** Feed the analysis layer a fabricated time series with a known injected step and known noise, and assert the anomaly detection recovers the injected step. This is the same pattern as validating the B-Raspi SNR estimator against synthetic signals of known SNR — reuse the approach.

---

## 10. Deliverables

1. **GitHub repository** — SNAP graph XML, batch runner, Python analysis package, pytest suite, GitHub Actions workflow, product manifest, environment definition. Phase 0 already contributes `s1_recon.py`, a 52-test suite, the CI workflow and the AOI definition.
2. **Requirements document and verification matrix** — matching the B-Raspi format.
3. **Technical report** — abstract, methods, results, discussion; every figure reproducible from committed code.
4. **`PREDICTION.md`** — the registered forward prediction, its criterion, and its verification date, committed before outcome publication.
5. **Nonconformance log** — already open with four entries from phase 0 (§15).
6. **A short README with two or three figures** — because most people will read only that.

---

## 11. Schedule

Part-time, evenings and weekends. Roughly four weeks to the report, plus a verification step months later.

| Phase | Work |
|:----------------------------------|:--------------------------------------------------------------------------------------------------|
| **0. Reconnaissance** — ✅ *complete, 8 Sept 2026* | CDSE registered; `s1_recon.py` written, tested (52 tests, CI green) and run; 499 products catalogued across 2024–26; orbit 1 ascending selected; baseline year settled. Carried into phase 1: download the National Land Cover Map and the Met Éireann Oak Park series. See §5 and §15. |
| **1. Pipeline** — *part done, 9–10 Sept* | Done: SNAP graph built, corrected and verified on one scene; `verify_scene.py` written; incidence angle measured (37.67° at Oak Park, S1D). Remaining: run the four cross-calibration scenes (§5), wrap the graph in a download → process → delete-raw batch runner, containerise, extend pytest and CI to the processing layer. |
| **2. Bulk processing** — *one evening* | Run the full scene list: 82 scenes, ~66 min of compute, ~145 GB of download. Bandwidth-bound, not compute-bound. Monitor, handle failures, log. Unattended — this is where the headless design pays for itself. |
| **3. Analysis** — *~6 days* | Extract per-class time series, compute the derived observables, test H1–H4, produce figures, run the inter-platform consistency check, and check the per-class incidence distributions (REQ-19). |
| **4. Prediction** — *~1 day* | Derive the recovery index, write and commit `PREDICTION.md`. |
| **5. Report and polish** — *~5 days* | Write the technical report, complete the verification matrix, tidy the repo and README. |
| **6. Verification** *(later)* — *Q1–Q2 2027* | When Teagasc's fodder survey and the CSO crop figures publish, verify the prediction and commit an addendum — whether it was right or wrong. |

**Do not skip phase 6.** It is what makes the prediction real, and it is the sentence that will actually get discussed at interview.

---

## 12. Risk register

| Risk | Mitigation |
|:---------------------------------------------------------------|:---------------------------------------------------------------|
| **R1** ✅ *closed* — Relative orbit numbering broken by the June 2026 reconfiguration | Did not materialise. Relative orbit 1 has continuous, fully-covering ascending acquisitions across 2024, 2025 and 2026. Settled empirically in phase 0. |
| **R2** (M/M, reduced) — Inter-platform radiometric offset between S1A, S1C and S1D contaminates the anomaly | Reduced from M/H: the platforms interleave within seasons on orbit 1, so REQ-09 can compare them inside stable ≤14-day windows rather than across a season boundary. Carry the measured offset explicitly; nonconformance if uncorrectable. |
| **R3** ✅ *closed* — Disk exhaustion | Closed by measurement. At 48 s per scene the download → process → delete-raw stream never holds more than two or three raw products: peak disk under 10 GB against a 145 GB total. |
| **R4** (L/M, reduced) — Single baseline year proves too noisy to support any claim | Baseline set to 2025 (§5). Measured throughput makes 2024 cost 13 min and 28 GB, so it is now included as a secondary check rather than held in reserve. Its 12-day cadence still makes it secondary, not a co-baseline. |
| **R5** (H/M) — Land cover map is 2018 and crop rotation has since changed the arable parcels | Use the arable class as an indicative stratum, not a crop-type map. State the limitation. Grassland is far more stable in Ireland, so lean the headline result on grassland. |
| **R6** (H/L) — Wet-canopy or rainfall-contaminated acquisitions distort individual dates | REQ-12 flagging; exclude or discuss, do not silently drop |
| **R7** (M/L) — Drought signal is not separable from normal senescence over arable | This is H2. If it fails it becomes the discussion, not a project failure. |
| **R8** (H/M) — Scope creep into Tier B or C mid-project | Requirements are frozen at the start of phase 1. Anything else goes in a "future work" section. |
| **R10** (H/M, raised) — Tooling defects produce plausible wrong numbers rather than errors | **Seven** such defects now found across phases 0 and 1 (§15) — this is the dominant failure mode of the project, not an occasional one. Every metric that drives a decision gets a test that pins it; exception handlers are narrowed so coding errors fail loudly; and no output is trusted because it ran without raising. |
| **R11** (M/M) — Incidence-angle gradient across the AOI is confounded with land cover | Measured: 10.45° spread, ~1.6 dB. Cancels between dates on one orbit but not necessarily between classes. REQ-19 tests the per-class distributions before any class comparison is reported. |
| **R9** (M/L) — Prediction turns out wrong | Publish it anyway, with the analysis of why. A verified-and-wrong prediction, honestly reported, is worth more than a vague claim that was never testable. |

Likelihood / impact shown as L/I, each H, M or L.

**Retired:** the SAFE vs COG_SAFE container concern raised at rev. 1 did not materialise — all 499 catalogued products are plain SAFE, so no `COG2GRD` conversion step is needed.

---

## 13. Growth path

Deliberately out of scope now, listed so the architecture does not preclude them:

- **A wet control AOI in Mayo.** Belmullet had 106% of average rainfall while Carlow had 73%. Running the identical pipeline over an unaffected region is a proper experimental control and would strengthen every claim in the report. **The cost argument for deferring this is now gone** — at 48 s a scene, a second AOI roughly doubles processing to about two hours. It remains out of Tier A scope under R8, but it is the first thing to add and the decision point is the end of phase 3, not now.
- **Sentinel-2 NDVI and NDMI cross-validation.** Independent optical confirmation of the SAR-derived signal, and a chance to quantify how many usable optical dates Irish cloud actually allows — which is itself a publishable-quality argument for SAR.
- **InSAR coherence from SLC.** 6- and 12-day coherence rises with drying and senescence. It is an observable optical cannot give at all, and it is the strongest available demonstration of SAR understanding.
- **Radiometric terrain flattening to γ°** instead of σ°.
- **A supervised-learning layer** over the multi-year, multi-index feature set — which would simultaneously close the machine-learning gap listed in section 10 of the experience bank.

---

## 14. How this lands on the CV

If completed to plan, this project supports the following additions to the experience bank:

- **§5, Flagship projects** — a second entry alongside B-Raspi: an applied SAR / Earth-observation analysis with its own requirements set, verification matrix, CI-tested pipeline and technical report.
- **§6, Skills inventory** — Sentinel-1 GRD processing, SNAP GPT batch automation, backscatter time-series analysis, geospatial Python (rasterio, geopandas), raster–vector stratification, EO data engineering at scale.
- **§9, Competency map** — upgrades *Remote sensing* from coursework to applied work, and adds a third instance to *Simulation & modelling* under the predicted-versus-measured pattern.
- **§10, Gaps** — closes the SAR / radar gap properly. Reduces it from "coursework only" to "one applied project, publicly verifiable".

The single sentence this project is being built to earn: *"I processed three seasons of Sentinel-1 over the 2026 Irish drought through a pipeline I built, made a dated prediction from the recovery signal, and published whether it was right."*

---

## 15. Nonconformance log

Kept because a verification record with real entries and root causes is worth more than an empty one. All four were found by running the tool against real catalogue data, not by inspection.

**NCR-01 — Coverage judged per product instead of per acquisition.**
*Observed:* the first phase 0 run reported "no fully viable orbit"; every candidate failed on minimum coverage, orbit 1 at 0.017.
*Cause:* Sentinel-1 GRD is sliced along-track, so one pass can arrive as two products that each clip only part of the AOI. The check demanded full coverage from every product.
*Fix:* `merge_slices` unions same-orbit, same-date footprints before judging coverage. Orbit 1 moved from 0.017 to 0.9999 and the correct answer fell out immediately.
*Verification:* two tests, one asserting that neither slice covers the AOI alone and that their union does. Now REQ-18.

**NCR-02 — Missing import masked by an over-broad exception handler.**
*Observed:* after the NCR-01 fix, union coverage was reported as the best single slice rather than the true union.
*Cause:* a patch silently failed to add the `shapely.wkt` import; the resulting `NameError` was caught by a bare `except Exception` around the WKT parse, which took the documented fallback path instead of failing.
*Fix:* import added; the handler narrowed to `ShapelyError`, so unparseable geometry is still tolerated but a coding error now fails loudly.
*Note:* this produced a plausible wrong number, not an error — the same silent-failure class the B-Raspi test design was built to catch.

**NCR-03 — Crash on non-contiguous slice unions.**
*Observed:* `AttributeError: 'MultiPolygon' object has no attribute 'exterior'` on the full 2024–26 run.
*Cause:* slices that do not touch union to a MultiPolygon; the edge-margin calculation assumed a Polygon. The earlier smoke test used a geometry where the union was always a single Polygon, so the branch was never exercised.
*Fix:* `.boundary` in place of `.exterior`. An `n_parts` field now records non-contiguous acquisitions so they can be excluded deliberately rather than silently averaged. Now REQ-17.
*Verification:* three tests, including a merge of genuinely disjoint slices.

**NCR-04 — Acquisition gap under-reported by one day.**
*Observed:* orbit 1's 2024 maximum gap reported as 23 days; the calendar gap between 26 June and 20 July 2024 is 24.
*Cause:* the gap was measured as an elapsed `timedelta`. Successive passes on one relative orbit drift a second or two earlier each cycle, so `.days` truncates.
*Fix:* gaps measured on calendar dates. Regression test pins both the old wrong value and the correct one. Now REQ-18.
*Impact:* none on the orbit decision, but the figure appeared in phase 0 output and would have been quoted.

**NCR-05 — GUI band selection silently reduced the chain to one polarisation.**
*Observed:* the graph exported from SNAP Graph Builder carried `selectedPolarisations = VH` in both ThermalNoiseRemoval and Calibration, and `sourceBands = Sigma0_VH` in Subset.
*Cause:* a single highlighted band in the operator UI is interpreted as "process only this one". The setting propagated into three nodes without warning.
*Impact if undetected:* no σ°VV, therefore no cross-ratio and no RVI — H1, H3 and half of H2 unanswerable. The output would have looked entirely normal, just with one band.
*Caught:* reviewing the exported XML before the batch, not by running it.
*Fix:* `VV,VH` in both operators, band list cleared in Subset. `verify_scene.py` now hard-fails on a missing band.

**NCR-06 — Verification tested the AOI against the raster bounding box, not the data.**
*Observed:* the first scene passed "AOI inside raster" with 12–14 km margins on all four sides, while σ° was valid over only 53.6% of the raster and incidence angle over 72.2%.
*Cause:* a terrain-corrected subset is a rotated quadrilateral inside a north-up bounding box. Bounds containment says nothing about whether the AOI has data. The same routine also labelled whole-raster incidence statistics as "across the AOI".
*Fix:* the AOI is rasterised and each band's valid fraction within it is a hard check; all statistics are AOI-restricted, with scene-wide values reported separately. Now REQ-18.
*Outcome:* the real scene passes at 100% AOI coverage — the 4 km subset buffer does survive the ~30° rotation. The check was still wrong.

**NCR-07 — AOI area reported 100× too large.**
*Observed:* `AOI covers 16,000,000 pixels (160000 km2)`. Sixteen million 10 m pixels is 1,600 km².
*Cause:* unit conversion written with a factor of 1e-4 instead of 1e-6.
*Fix:* corrected. The mask itself was right; only the printed figure was wrong.

**NCR-08 — `rstrip('.SAFE')` strips a character set, not a suffix.**
*Observed:* caught in review before it ran. `"..._0041C9_702F.SAFE".rstrip(".SAFE")` yields `..._0041C9_702`, because `rstrip` removes any trailing character in `{'.','S','A','F','E'}` until one is not.
*Cause:* a Python API whose name reads like "remove this suffix" and is not.
*Fix:* `removesuffix`. One of the four cross-calibration products would have been silently misnamed.

**NCR-09 — Batch failures reported the last line of a Java stack trace.**
*Observed:* all four cross-calibration scenes recorded `gpt exit 1: at com.install4j.runtime.launcher.WinLauncher.main(WinLauncher.java:25)` — true, and useless. The real message, `Error: ..\\graphs\\s1_grd_preprocess_v2.xml (The system cannot find the path specified)`, was three lines above.
*Cause:* the error extractor took the last non-empty line of stderr. Java prints the message first and the trace after it, so the last line is always the innermost frame.
*Fix:* `gpt_error()` scans for the message line. Cost: one 13-minute download cycle diagnosed as a processing bug when it was a missing file.

**NCR-10 — No preflight; a missing graph file surfaced after 13 minutes of downloading.**
*Observed:* the batch downloaded 7 GB, then failed every scene on a path that could have been checked in microseconds.
*Cause:* the runner validated nothing before starting work.
*Fix:* `preflight()` checks the graph, the AOI, the `gpt` executable and the `verify_scene` import before the first byte is fetched. The `verify_scene` import was also moved inside the per-scene `try`, so a bad import fails one scene rather than the run.

**NCR-11 — `requirements.txt` was out of date; pip reported success while the dependency was never installed.**
*Observed:* `pip install -r requirements.txt` succeeded twice in a fresh venv, and `import rasterio` still failed. The file was the original three-line version and never listed rasterio, pyproj or numpy. The tool's own error message advised running the command that had just succeeded.
*Cause:* the manifest drifted behind the code, and the diagnostic assumed the manifest was correct.
*Fix:* six-line `requirements.txt`; `listed_in_requirements()` distinguishes "not installed" from "not even asked for" and names the stale file. A diagnostic that can only recommend one action will recommend it when it is wrong.

**NCR-12 — Terrain-Correction ran with `alignToStandardGrid=false`.**
*Observed:* the two cross-calibration pairs sit 0.421 and 0.293 pixels off a common lattice.
*Cause:* with the flag off, SNAP takes each output's origin from that scene's own reprojected footprint. Footprints differ scene to scene, so every acquisition lands on a slightly different 10 m grid.
*Consequence if undetected:* harmless for per-scene statistics — which is all phase 1 did, which is why five verified scenes and a passing test suite never touched it. Fatal for phase 3, which is a per-pixel time series: 82 acquisitions on 82 grids would need resampling onto a common lattice, degrading σ⁰ 82 times to recover something that was free at processing time.
*Fix:* graph v3 sets it true; `standardGridOriginX/Y` were already 0.0, so origins snap to multiples of the 10 m pixel spacing in EPSG:2157 and all acquisitions share one grid. The four cross-calibration scenes are reprocessed before the batch.
*Note:* found by a tool written to measure something else. `crosscal.py` had to align two rasters to compare them, so it reported the misalignment as a by-product.

**NCR-13 — Flatness test flagged scatter as a slope.**
*Observed:* `crosscal.py` reported "NOT flat; a geometric term is still in this number" for pair-A σ⁰VV, on a bin spread of 0.176 dB.
*Cause:* the test was a bare threshold on spread. A genuine geometric residual varies monotonically with incidence angle; the observed bins rise across three bands and fall in the fourth. The AOI's incidence distribution is peaked near 37.7°, so the 34–36° and 40–42° bins hold small, land-cover-skewed samples that wander. The threshold itself was also set below the measurement's own one-day confound.
*Fix:* flag only a spread that is both large **and** monotonic; print the pixel count beside each bin so a thin tail is visible as thin.
*Class:* a verification tool raising a false alarm is not harmless. It spends the attention that a real alarm needs, and a tool that cries wolf gets ignored exactly when it should not be.

**Process note.** Thirteen nonconformances, and **not one is an algorithm.** The SAR processing has been correct since the first scene. Four root causes recur:

*(a) Batched string replacements applied without asserting each one matched* — NCR-02, NCR-03. Every subsequent edit asserts its match count before applying.

*(b) Correct computation, wrong presentation* — NCR-04, NCR-06, NCR-07, NCR-09, NCR-13. Labelling, unit and diagnostic errors sitting on arithmetic that was already right. These survive review, because the code looks correct and the number looks plausible. The only defence found so far is checking output values against an independently known quantity — 16 million 10 m pixels *must* be 1,600 km², a 40 km AOI *must* be 1,600 km², and the mismatch is then obvious.

*(c) Configuration and environment* — NCR-05, NCR-10, NCR-11, NCR-12. A GUI default, a missing preflight, a stale manifest, a flag left false. All cheap to find early and expensive to find late; NCR-12 in particular would have cost the entire batch.

*(d) A standard-library method that does not do what its name says* — NCR-08.

The pattern worth carrying forward: **the failure mode of this project is not getting the physics wrong, it is getting the plumbing wrong and not noticing.** Every defence that has actually worked — checking a printed number against an independently known quantity, asserting a patch matched, verifying before deleting, preflighting before downloading — is a check on plumbing, not on radar.

---

## 16. Phase 0 open questions — closed

1. **Do relative orbit numbers over Ireland survive the June 2026 reconfiguration, and is there a single orbit with continuous coverage across 2024–2026?** Yes to both. Orbit 1 ascending has fully-covering acquisitions in all three seasons. *(R1 closed.)*
2. **From what date is Sentinel-1C available over Ireland, and does it overlap S1A enough to cross-calibrate directly?** S1C appears on orbit 1 from 4 April 2025 and runs alternating with S1A on a 6-day offset until S1A's last pass on 28 June 2026. S1D joins 24 April 2026. The overlap is ample — direct inter-platform comparison inside ≤14-day windows is possible throughout, which is why REQ-09 was rewritten.
3. **Does Met Éireann's soil moisture deficit series for Oak Park cover 2024–2026 continuously, and at which drainage classes?** Still open — carried into phase 1. Met Éireann publishes daily SMD for three soil drainage classes at synoptic stations; continuity for station 375 needs checking on download.
4. **Is the National Land Cover Map arable class fine-grained enough to give ≥1000 pixels per class per date after buffering?** Still open — carried into phase 1, resolved when the map is downloaded and clipped to the AOI. Note the AOI holds 16 million 10 m pixels, so the 1000-pixel floor is unlikely to bind; the real question is now whether the two classes span the same incidence-angle range (REQ-19).
5. **Ascending or descending, and does overpass time matter for dew?** Settled: ascending, orbit 1, ~19:15 local. The descending candidates pass at ~07:40 local, which is peak dew on Irish grassland in summer and biases backscatter in the same direction as the drought signal. See §5.

Two of five remain, both about ancillary data rather than the SAR configuration. Neither blocks the cross-calibration run or the bulk batch; both must close before phase 3 analysis.
