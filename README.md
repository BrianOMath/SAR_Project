# Sentinel-1 SAR analysis of the 2026 Irish drought

Detection limits of Sentinel-1 C-band cross-ratio for drought monitoring over
mixed farmland, Co. Carlow. 156 acquisitions, six seasons, one frozen orbital
configuration, 302 automated tests.

**Status:** pipeline complete and validated. One result below p = 0.05, awaiting
a confirmatory run on 2018 — see [`REMAINING_WORK.md`](REMAINING_WORK.md).

---

## What this is

Ireland had an exceptional drought in summer 2026. At Oak Park, Co. Carlow, it
was the second most severe in the 23-year soil-moisture record and Teagasc
measured grass production 412 kg DM/ha below the five-year average.

This project asks whether that impact is visible in Sentinel-1 radar, and — when
the first answers came back null — what the measurement's actual detection limit
is. The headline numbers:

| | |
|:--|:--|
| Pipeline repeatability | **τ = 0.000 dB/month** across five years and four platforms |
| Inter-platform calibration | 0.171 dB worst channel; **0.011 dB** in the cross-ratio |
| Per-acquisition noise floor | 0.63 dB, whole-AOI |
| Detection limit | an **81%** change in senescence rate; the drought produced **38%** |

A secondary finding with wider application: **a control works by being similar,
not by being inert.** A dry-versus-wet grassland contrast on 49,000 pixels beat
a grassland-versus-forest contrast on 3.9 million, by a factor of two.

## Documents

| | |
|:--|:--|
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Requirements, frozen configuration, risk register, 16-entry nonconformance log |
| [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md) | The scientific write-up — methods, results, sensitivity analysis |
| [`METHODS_LOG.md`](METHODS_LOG.md) | Why the method changed seven times, with the superseded results preserved |
| [`REMAINING_WORK.md`](REMAINING_WORK.md) | What is left, in dependency order |

## Reproducing from a clean clone

```bash
git clone <repo> && cd SAR_Project/S1_Recon
python -m venv .venv && .venv/Scripts/activate   # Windows
python -m pip install -r requirements.txt
python -m pytest -q                               # 302 tests
```

Credentials for the Copernicus Data Space Ecosystem go in the environment, never
on the command line — it lands in shell history:

```powershell
$cred = Get-Credential -Message 'CDSE login'
$cred | Export-Clixml "$env:USERPROFILE\.cdse.xml"
```

SNAP must be installed and `gpt` on the path. Expect ~170 GB of disk for the
full six-season archive.

## The pipeline, in order

| script | does | output |
|:--|:--|:--|
| `s1_recon.py` | Queries CDSE, scores every orbit on coverage, gaps, slicing and volume | `recon_out/scenes.csv` |
| `batch_process.py` | Download → SNAP `gpt` → verify → delete raw, resumable | `C:/sar/proc/*.dim` |
| `verify_scene.py` | Per-scene gate: bands, CRS, AOI against the **valid-data mask**, linearity | exit 0/1 |
| `crosscal.py` | Inter-platform offsets from consecutive-day pairs (REQ-09) | `results/phase1/` |
| `fetch_landcover.py` | NLCM polygons, burned onto the stack's own pixel grid | `data/landcover/` |
| `build_series.py` | 156 scenes → one row per acquisition | `results/phase2/series.csv` |
| `fetch_met.py` | Met Éireann daily data; derives and **freezes** the drought window | `results/phase4/drought_window.json` |
| `stratify.py` | Stratified difference-in-differences against a baseline distribution | `results/phase3/` |
| `figures.py` | The four report figures, recomputed from the CSVs | `results/figures/` |

A full run:

```powershell
python s1_recon.py --aoi aoi_oakpark.geojson --years 2021 2022 2023 2024 2025 2026 `
    --orbit-direction ASCENDING --out recon_out

python batch_process.py recon_out/scenes.csv --graph ../graphs/s1_grd_preprocess_v3.xml `
    --aoi aoi_oakpark.geojson --out C:/sar/proc --raw C:/sar/raw --years 2021 2022 2023 2024 2025 2026

python fetch_landcover.py --aoi aoi_oakpark.geojson --reference C:/sar/proc/20260717_S1D.dim `
    --out ../data/landcover --csv ../results/phase3/landcover_areas.csv

python build_series.py C:\sar\proc --aoi aoi_oakpark.geojson --csv ../results/phase2/series.csv

python fetch_met.py --station 375 --out ../data/met --window ../results/phase4/drought_window.json

python stratify.py C:\sar\proc --aoi aoi_oakpark.geojson `
    --classes ../data/landcover/nlcm_2018_classes.tif `
    --areas ../results/phase3/landcover_areas.csv --erode 2 --out ../results/phase3 `
    --window-from ../results/phase4/drought_window.json
```

## Three decisions worth knowing before reading the code

**σ⁰ is stored and averaged in linear power, never dB.** The mean of a logarithm
is not the logarithm of a mean, and the error is systematic. A test in
`test_build_series.py` demonstrates it on this data's shape: −12.6 dB averaged
correctly, −15.0 dB averaged in dB. REQ-06.

**`alignToStandardGrid=true`.** With it false, every acquisition lands on its own
10 m lattice and no two rasters stack without resampling. Invisible to per-scene
checks; fatal to a time series. NCR-12.

**Any analysis window must come from data independent of the SAR**, be written to
the repository with its rule and a timestamp, and be frozen before the test runs.
REQ-20. `drought_window.json` is that record.

## Data and licences

Copernicus Sentinel-1 2016–2026, processed by ESA, retrieved from the
[Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/).
National Land Cover Map of Ireland 2018 © Tailte Éireann and the Environmental
Protection Agency, CC BY 4.0. Daily climate data © Met Éireann, CC BY 4.0.
Grass production figures from Teagasc PastureBase Ireland.

Raw Sentinel-1 products are not committed (REQ-16). `recon_out/scenes.csv` is
the manifest and is sufficient to re-download the archive — it is kept in version
history because the CDSE catalogue is not static.
