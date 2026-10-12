# T1 overnight runbook — the 2018 confirmatory run

Brian Ó Mathúna · 12 October 2026

Run the blocks in order. **Block 0 must be committed before Block 3 starts** —
that is the whole point of the exercise. Blocks 0–2 take about twenty minutes of
attention, Block 3 runs unattended, Blocks 4–6 are the morning's work.

---

## Block 0 — Freeze the hypothesis, then commit it

Copy into the repo root:

- `PREREGISTRATION_2018.md`

Copy into `S1_Recon/`:

- `ipf_check.py`
- `test_ipf_check.py`

Then stage, **one path per line** — `git add` is atomic and a single bad
pathspec aborts the whole command:

```powershell
cd <repo root>

git add PREREGISTRATION_2018.md
git add README.md
git add METHODS_LOG.md
git add REMAINING_WORK.md
git add S1_Recon/ipf_check.py
git add S1_Recon/test_ipf_check.py
```

Check the plan in the repo is rev. 5 (58,665 bytes) and not rev. 4 (50,795):

```powershell
(Get-Item PROJECT_PLAN.md).Length
Get-Content PROJECT_PLAN.md -TotalCount 4 | Select-Object -Last 1
```

If it still says rev. 4, copy rev. 5 in and `git add PROJECT_PLAN.md`.

```powershell
git status
git commit -m "Pre-register the 2018 confirmatory test before processing 2016-2020

The 2026 window result is one test at p = 0.0398 among thirty-six, where 1.8
such results are expected by chance. This fixes the hypothesis, the baseline
membership rule, the decision thresholds and the meaning of each outcome
before any 2016-2020 product is downloaded.

Adds ipf_check.py: reads the IPF processor version out of each .dim header,
so the processor baseline can be audited after the raw products are deleted.
38 tests.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CSdEUv6cyW6yXxN8w3sVCo"

git push
```

**The push is the timestamp.** A pre-registration that lives only on your disk
proves nothing; one in GitHub's commit history is dated by a third party. Watch
CI — `matplotlib` and `scipy` were new in the last commit, and this one adds a
test file.

---

## Block 1 — Pre-flight, five minutes

### Disk

```powershell
Get-Volume | Select-Object DriveLetter, FileSystemLabel,
    @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,1)}},
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}

"{0:N1} GB in proc" -f ((Get-ChildItem C:\sar\proc -Recurse -File |
    Measure-Object Length -Sum).Sum / 1GB)
```

Full scope needs the proc volume to reach **~170 GB**, so about **86 GB free**
on top of what is there now.

**If C: has it, change nothing.** If it does not, move the *existing* proc
folder to the SSD before starting, not just the new output:

```powershell
robocopy C:\sar\proc E:\sar\proc /E /MOVE /NFL /NDL /NJH /R:1
```

Splitting the stack across two volumes is the failure mode to avoid —
`build_series.py` and `stratify.py` each take one directory, and a half-stack
produces a plausible-looking answer from the wrong data. Everything on one
volume, or nothing moved.

If the disk will not stretch, drop to **2017–2019** (~56 GB). The
pre-registration already handles this: any year not processed is dropped from
the baseline set and the omission recorded, so a narrower scope costs
statistical power and nothing else. Nine baselines give t = 2.306; seven give
t = 2.447.

### Stop the machine sleeping

A ten-hour run dies at the first standby. This is the single most likely way to
lose the night:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
```

Write down the current values first if you want them back:

```powershell
powercfg /query SCHEME_CURRENT SUB_SLEEP | Select-String "Current AC"
```

### Credentials and tools

```powershell
$env:CDSE_USER.Length          # non-zero, and don't echo the password
$env:CDSE_PASSWORD.Length
gpt -h | Select-Object -First 2
cd S1_Recon
python -m pytest -q            # expect 340 now
```

### Confirm the flags the morning needs actually exist

Thirty seconds now, rather than finding out at 08:00 with the data already on
disk:

```powershell
python fetch_met.py --help | Select-String "year|window|local"
python stratify.py --help | Select-String "treat-year|base-years|window-from|metric"
python ipf_check.py --help | Select-Object -First 3
```

`fetch_met.py` needs `--year`; `stratify.py` needs `--treat-year`,
`--base-years` and `--window-from`. If any is missing, tell me before you start
the batch — the fix is small but it is not something to discover tired.

---

## Block 2 — Recon the whole record, and read it before downloading 140 GB

One pass over 2016–2026 so `scenes.csv` is the manifest for the entire series
rather than two files that have to be reconciled later:

```powershell
python s1_recon.py --aoi aoi_oakpark.geojson `
    --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
    --orbit-direction ASCENDING --out recon_out
```

**Stop and look at the output.** Three things decide whether the night is worth
starting:

1. **Relative orbit 1 still wins.** It has been the frozen configuration since
   phase 0; if the eleven-year scoring now favours a different orbit, that is a
   finding to discuss, not an excuse to switch — switching would break
   comparability with the 156 scenes already processed.
2. **2018 coverage is 1.0000** across its acquisitions. Anything less and the
   confirmatory test is weaker than the one it is confirming.
3. **No year has a limb gap over ~18 days** inside roughly DOY 180–250. A year
   with a three-week hole through the senescence limb cannot support a slope
   fit and should be dropped from the baseline set now, in writing, rather than
   after seeing its result.

2016 deserves a specific look: Sentinel-1B launched in April 2016 and reached
routine operations over the following months, so early-2016 orbit 1 may be
6-day only from mid-season. If 2016 fails the gap check, drop it and note it.

```powershell
Import-Csv recon_out/scenes.csv | Group-Object {$_.date.Substring(0,4)} |
    Select-Object Name, Count
```

---

## Block 3 — The batch, unattended

Dry run first. Already-verified scenes skip, so this should report only the new
years:

```powershell
python batch_process.py recon_out/scenes.csv `
    --graph ../graphs/s1_grd_preprocess_v3.xml `
    --aoi aoi_oakpark.geojson --out C:/sar/proc --raw C:/sar/raw `
    --years 2016 2017 2018 2019 2020 --dry-run
```

Confirm the count is ~160 and not ~320 — a count near the full record means it
is not recognising the existing output and you would be reprocessing six years
you already have.

Then the real thing, with a transcript:

```powershell
python batch_process.py recon_out/scenes.csv `
    --graph ../graphs/s1_grd_preprocess_v3.xml `
    --aoi aoi_oakpark.geojson --out C:/sar/proc --raw C:/sar/raw `
    --years 2016 2017 2018 2019 2020 2>&1 |
    Tee-Object -FilePath ../results/phase0/t1_batch.log
```

**Graph v3, not v2.** v2 is retained only as NCR-12 evidence; running it would
put these scenes on their own lattices and `build_series.py` would refuse the
stack in the morning — after ten hours of processing.

Leave it. Go to bed.

---

## Block 4 — Morning: did it finish, and on what processor?

```powershell
Select-String -Path ../results/phase0/t1_batch.log -Pattern "fail|error|exclude" |
    Select-Object -Last 30

(Get-ChildItem C:\sar\proc -Filter *.dim).Count     # expect ~316
```

Anything that failed keeps its raw product and logs the reason — that is the
verification gate working, not a problem to paper over. Re-run the same batch
command to retry only the failures.

Then the processor baseline:

```powershell
python ipf_check.py C:\sar\proc --csv ../results/phase0/ipf_versions.csv
```

2018 will very likely sit on IPF 2.84 or 2.90 and 2026 on 3.7x, so expect the
script to report that the series straddles a thermal-noise change. **That is
anticipated, not a failure.** It cancels in a same-image spatial contrast,
because grassland and forest are measured in the same image with the same noise
vectors — the identical argument that makes inter-platform calibration
irrelevant to these contrasts. It does affect the absolute σ⁰ series, and the
report must say so.

The one result worth a second look is a **mixed version inside a single year**.
The contrasts still protect against it, but the per-year slope fits do not, and
a mid-season step in the noise floor is exactly the shape a drought signal has.

---

## Block 5 — Series, then freeze 2018's window before any test touches it

```powershell
python build_series.py C:\sar\proc --aoi aoi_oakpark.geojson `
    --csv ../results/phase2/series.csv
```

If this refuses to write, the lattice check caught something — read the message
rather than working around it. That refusal is NCR-12's fix doing its job.

Now derive 2018's window **by the same rule**, into its own file:

```powershell
python fetch_met.py --station 375 --out ../data/met --year 2018 `
    --window ../results/phase4/drought_window_2018.json

Get-Content ../results/phase4/drought_window_2018.json
```

Check the JSON names the same rule as the 2026 file (longest spell with
moderately drained SMD ≥ 50 mm for ≥ 10 days) and carries its timestamp. 2018
had 102 days above threshold against 2026's 65, so expect a longer window —
likely starting in late June and running past mid-September.

**Commit it before running Block 6:**

```powershell
cd <repo root>
git add results/phase4/drought_window_2018.json
git commit -m "Freeze the 2018 drought window before any SAR test reads it (REQ-20)

Derived from Met Eireann station 375 by the identical rule used for 2026.
No SAR input.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CSdEUv6cyW6yXxN8w3sVCo"
git push
cd S1_Recon
```

This is REQ-20 made structural rather than promised. The window is in a
third party's commit history before the test that uses it has been run.

---

## Block 6 — The test

The confirmatory one first, cross-ratio, nine baselines. Adjust `--base-years`
to drop any year Block 2 disqualified:

```powershell
python stratify.py C:\sar\proc --aoi aoi_oakpark.geojson `
    --classes ../data/landcover/nlcm_2018_classes.tif `
    --areas ../results/phase3/landcover_areas.csv --erode 2 `
    --out ../results/phase3 `
    --window-from ../results/phase4/drought_window_2018.json `
    --treat-year 2018 `
    --base-years 2016 2017 2019 2020 2021 2022 2023 2024 2025 `
    --metric cr_db
```

Read `grassland − forest` and nothing else first. The pre-registration says
CONFIRMED needs both a steeper slope than baseline **and** z ≤ −2.306, and the
point prediction is a ratio ≥ 1.5 against an expected 2.1.

Then the secondary observables and the re-test of 2026 on the wider baseline:

```powershell
python stratify.py ... --metric vv_db          # same flags otherwise
python stratify.py ... --metric vh_db

python stratify.py C:\sar\proc --aoi aoi_oakpark.geojson `
    --classes ../data/landcover/nlcm_2018_classes.tif `
    --areas ../results/phase3/landcover_areas.csv --erode 2 `
    --out ../results/phase3 `
    --window-from ../results/phase4/drought_window.json `
    --treat-year 2026 `
    --base-years 2016 2017 2019 2020 2021 2022 2023 2024 2025 `
    --metric cr_db
```

That last command is the same test as before with four more baseline years, not
a new question. Expect the interval to narrow: df goes from 4 to 8 and the
critical value from 2.776 to 2.306. Report both the five-year and nine-year
versions.

Also check the leave-one-out calibration in each run. If a baseline year now
sits outside its own prediction interval, the baseline is not homogeneous and
that matters more than the headline.

---

## Afterwards

```powershell
powercfg /change standby-timeout-ac 30      # or whatever you noted in Block 1
```

Send me the output of Block 4 and Block 6 and we will do T3 and T4 — the report
to rev. 2 and the figures, including the 2018-against-2026 panel.

Whichever way it lands. That is written down now.
