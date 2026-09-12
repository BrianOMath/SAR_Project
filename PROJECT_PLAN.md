# SAR-Bog: Radar signatures of the 2026 Irish drought

**Project plan — Tier A (minimum viable scope)**
Brian Ó Mathúna · drafted 7 September 2026 · rev. 2, 8 September 2026
**Phase 0 complete — data configuration locked (§5)**

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

## 5. Phase 0 result — the data configuration (locked)

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
| REQ-18 | Coverage, gap and completeness metrics shall be computed per acquisition (slices merged) and on calendar dates, never per product or on elapsed timedeltas. | T |

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

- **The inter-platform consistency check (REQ-09).** Select stable, temporally invariant targets inside the AOI — a large conifer block, an urban or industrial surface. Phase 0 showed the platforms *interleave* on orbit 1 rather than switching once, so compare S1A against S1C against S1D within short windows where surface conditions are effectively constant, rather than either side of the 29 June 2026 termination. A 2025 fortnight typically holds one S1A and one S1C pass six days apart; the 2026 drought window alternates S1C and S1D. Report the offset in dB per polarisation with a confidence interval. Within the sensor's specified radiometric stability: say so and move on. Outside it: document a nonconformance and carry the offset explicitly. Either outcome is a result — and this design is materially stronger than the before/after comparison assumed at rev. 1.
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
| **1. Pipeline** — *~5 days* | Build the SNAP graph in the GUI on one orbit-1 scene, verify it visually, export to XML. Wrap in a batch runner with download, process, delete-raw streaming. Containerise. Extend the existing pytest suite and CI to the processing layer. Measure the true incidence angle over the AOI from the product annotation and record it. |
| **2. Bulk processing** — *~3 days, mostly waiting* | Run the full scene list. Monitor, handle failures, log. Largely unattended — this is where the headless design pays for itself. |
| **3. Analysis** — *~6 days* | Extract per-class time series, compute the derived observables, test H1–H4, produce figures, run the inter-platform consistency check. |
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
| **R3** (L/M, reduced) — Disk exhaustion | Now sized from real data: 66 acquisitions for 2025+2026 at ~118 GB, or 82 and ~146 GB including 2024. Orbit 1 needs mosaicking on 1 acquisition in 82, so there is no slice-pair overhead. Streaming pattern: download, process, delete raw, keep only the ~50 MB AOI subsets. |
| **R4** (M/M) — Single baseline year proves too noisy to support any claim | Baseline set to 2025 (§5). 2024 is available as a secondary check if phase 3 shows the noise floor is too high, at the cost of ~28 GB and a sparser 12-day cadence. Decide when the noise level is measurable, not now. |
| **R5** (H/M) — Land cover map is 2018 and crop rotation has since changed the arable parcels | Use the arable class as an indicative stratum, not a crop-type map. State the limitation. Grassland is far more stable in Ireland, so lean the headline result on grassland. |
| **R6** (H/L) — Wet-canopy or rainfall-contaminated acquisitions distort individual dates | REQ-12 flagging; exclude or discuss, do not silently drop |
| **R7** (M/L) — Drought signal is not separable from normal senescence over arable | This is H2. If it fails it becomes the discussion, not a project failure. |
| **R8** (H/M) — Scope creep into Tier B or C mid-project | Requirements are frozen at the start of phase 1. Anything else goes in a "future work" section. |
| **R10** (M/M) — Tooling defects produce plausible wrong numbers rather than errors | Three such defects already found in phase 0 (§15). Every metric that drives a decision gets a test that pins it; exception handlers are narrowed so coding errors fail loudly instead of falling back silently. |
| **R9** (M/L) — Prediction turns out wrong | Publish it anyway, with the analysis of why. A verified-and-wrong prediction, honestly reported, is worth more than a vague claim that was never testable. |

Likelihood / impact shown as L/I, each H, M or L.

**Retired:** the SAFE vs COG_SAFE container concern raised at rev. 1 did not materialise — all 499 catalogued products are plain SAFE, so no `COG2GRD` conversion step is needed.

---

## 13. Growth path

Deliberately out of scope now, listed so the architecture does not preclude them:

- **A wet control AOI in Mayo.** Belmullet had 106% of average rainfall while Carlow had 73%. Running the identical pipeline over an unaffected region is a proper experimental control and would strengthen every claim in the report. Cheapest possible upgrade — the pipeline already exists, it is only more scenes.
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

**Process note.** NCR-02 and NCR-03 share a root cause worth recording separately: batched string replacements applied without asserting that each one matched. Two patches silently did nothing. Every subsequent edit asserts its match count before applying.

---

## 16. Phase 0 open questions — closed

1. **Do relative orbit numbers over Ireland survive the June 2026 reconfiguration, and is there a single orbit with continuous coverage across 2024–2026?** Yes to both. Orbit 1 ascending has fully-covering acquisitions in all three seasons. *(R1 closed.)*
2. **From what date is Sentinel-1C available over Ireland, and does it overlap S1A enough to cross-calibrate directly?** S1C appears on orbit 1 from 4 April 2025 and runs alternating with S1A on a 6-day offset until S1A's last pass on 28 June 2026. S1D joins 24 April 2026. The overlap is ample — direct inter-platform comparison inside ≤14-day windows is possible throughout, which is why REQ-09 was rewritten.
3. **Does Met Éireann's soil moisture deficit series for Oak Park cover 2024–2026 continuously, and at which drainage classes?** Still open — carried into phase 1. Met Éireann publishes daily SMD for three soil drainage classes at synoptic stations; continuity for station 375 needs checking on download.
4. **Is the National Land Cover Map arable class fine-grained enough to give ≥1000 pixels per class per date after buffering?** Still open — carried into phase 1, resolved when the map is downloaded and clipped to the AOI.
5. **Ascending or descending, and does overpass time matter for dew?** Settled: ascending, orbit 1, ~19:15 local. The descending candidates pass at ~07:40 local, which is peak dew on Irish grassland in summer and biases backscatter in the same direction as the drought signal. See §5.

Two of five remain, both about ancillary data rather than the SAR configuration, and neither blocks phase 1.
