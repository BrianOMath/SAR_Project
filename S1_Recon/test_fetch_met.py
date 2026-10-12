"""Tests for the Met Éireann fetch and drought-window derivation (phase 4)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from fetch_met import (
    MIN_SPELL_DAYS,
    longest_spell,
    parse_daily,
    pick_column,
    rainfall_deficit,
    spells,
    to_date,
    to_float,
)

# A Met Éireann daily file: a human-readable preamble of arbitrary length,
# then the real header. The preamble is why the parser hunts for the header
# rather than skipping a fixed number of lines.
SAMPLE = """Station Name: OAK PARK
Station Height: 62 M
Latitude:52.861  ,Longitude: -6.913

date:  -  Date and Time (utc)
rain:  -  Precipitation Amount (mm)
smd_md: -  Moderately Drained Soil Moisture Deficit (mm)

date,ind,rain,maxtp,mintp,smd_wd,smd_md,smd_pd
01-jul-2026,0,0.0,24.1,11.2,38.2,31.4,20.1
02-jul-2026,0,0.0,25.3,12.0,43.1,36.0,24.4
03-jul-2026,0,2.4,19.8,13.1,41.0,33.9,22.0
04-jul-2026,0, ,21.0,12.4,45.5,38.1,26.2
"""


def test_header_is_found_after_a_variable_preamble():
    rows, cols = parse_daily(SAMPLE)
    assert cols[0] == "date"
    assert "smd_md" in cols
    assert len(rows) == 4


def test_preamble_lines_do_not_become_records():
    rows, _ = parse_daily(SAMPLE)
    assert all(to_date(r["date"]) is not None for r in rows)


def test_a_file_without_a_header_is_rejected_not_guessed():
    with pytest.raises(ValueError):
        parse_daily("Station Name: OAK PARK\n\nsome notes\n")


def test_values_parse():
    rows, _ = parse_daily(SAMPLE)
    assert to_float(rows[0]["smd_md"]) == pytest.approx(31.4)
    assert to_date(rows[0]["date"]) == date(2026, 7, 1)


# --- date and number handling ---------------------------------------------

@pytest.mark.parametrize("s,expected", [
    ("01-jul-2026", date(2026, 7, 1)),
    ("15-aug-2026", date(2026, 8, 15)),
    ("2026-07-01", date(2026, 7, 1)),
    ("01/07/2026", date(2026, 7, 1)),
])
def test_date_formats(s, expected):
    assert to_date(s) == expected


def test_unparseable_date_is_none_not_an_exception():
    assert to_date("not a date") is None
    assert to_date("") is None


def test_missing_values_become_nan_not_zero():
    # The failure that would matter: a blank rainfall day read as 0 mm
    # manufactures dry weather in the exact variable being measured.
    for blank in ("", " ", "n/a", "-", None):
        assert np.isnan(to_float(blank))
    assert to_float("0.0") == 0.0


# --- column selection ------------------------------------------------------

def test_moderately_drained_smd_is_preferred():
    # Irish grassland convention; the other drainage classes are fallbacks.
    assert pick_column(["date", "smd_wd", "smd_md", "smd_pd"],
                       ("smd_md", "smd_wd", "smd_pd")) == "smd_md"


def test_falls_back_to_another_drainage_class():
    assert pick_column(["date", "smd_pd"],
                       ("smd_md", "smd_wd", "smd_pd")) == "smd_pd"


def test_absent_column_is_none():
    assert pick_column(["date", "rain"], ("smd_md",)) is None


# --- spell detection -------------------------------------------------------

def days_from(start: date, n: int):
    return [start + timedelta(days=i) for i in range(n)]


def test_a_long_dry_spell_is_found():
    d = days_from(date(2026, 6, 1), 40)
    sp = spells(d, [10 <= i < 35 for i in range(40)])
    assert len(sp) == 1
    assert sp[0] == (date(2026, 6, 11), date(2026, 7, 5))


def test_a_short_spell_is_rejected():
    # A five-day dry spell is weather, not drought.
    d = days_from(date(2026, 6, 1), 30)
    assert spells(d, [10 <= i < 15 for i in range(30)]) == []


def test_two_spells_separated_by_rain():
    d = days_from(date(2026, 6, 1), 60)
    sp = spells(d, [(0 <= i < 15) or (30 <= i < 50) for i in range(60)])
    assert len(sp) == 2
    assert longest_spell(sp) == sp[1]


def test_a_spell_running_to_the_end_of_the_record_is_kept():
    # Off-by-one territory: a drought that had not broken by the last
    # observation must still be reported.
    d = days_from(date(2026, 6, 1), 30)
    sp = spells(d, [i >= 10 for i in range(30)])
    assert len(sp) == 1
    assert sp[0][1] == date(2026, 6, 30)


def test_spell_length_counts_both_endpoints():
    d = days_from(date(2026, 6, 1), 30)
    sp = spells(d, [i < MIN_SPELL_DAYS for i in range(30)])
    assert len(sp) == 1, "a spell of exactly the minimum length must qualify"


def test_no_spell_at_all():
    d = days_from(date(2026, 6, 1), 30)
    assert spells(d, [False] * 30) == []
    assert longest_spell([]) is None


# --- rainfall fallback -----------------------------------------------------

def test_rainfall_anomaly_detects_a_dry_year():
    days, rain = [], []
    for y, daily in ((2024, 3.0), (2025, 3.0), (2026, 1.0)):
        for i in range(214):                       # 1 Apr to 31 Oct
            days.append(date(y, 4, 1) + timedelta(days=i))
            rain.append(daily)
    out = rainfall_deficit(days, rain, 2026, [2024, 2025])
    assert out["max_deficit_mm"] < -300
    assert out["max_deficit_date"].startswith("2026-10")


def test_rainfall_anomaly_of_an_average_year_is_near_zero():
    days, rain = [], []
    for y in (2024, 2025, 2026):
        for i in range(214):
            days.append(date(y, 4, 1) + timedelta(days=i))
            rain.append(3.0)
    out = rainfall_deficit(days, rain, 2026, [2024, 2025])
    assert abs(out["max_deficit_mm"]) < 1e-6


def test_rainfall_anomaly_without_reference_years_returns_nothing():
    days = [date(2026, 4, 1) + timedelta(days=i) for i in range(100)]
    assert rainfall_deficit(days, [2.0] * 100, 2026, []) == {}




# --- --local resolution ----------------------------------------------------

from fetch_met import resolve_local                                # noqa: E402


def test_a_file_path_is_returned_unchanged(tmp_path):
    f = tmp_path / "dly375.csv"
    f.write_text("date,rain\n")
    assert resolve_local(f) == f


def test_a_directory_with_one_csv_resolves_to_it(tmp_path):
    # The real case: Windows raises PermissionError when a directory is opened
    # as a file, which reads as a security problem and is not one.
    f = tmp_path / "dly375.csv"
    f.write_text("date,rain\n")
    assert resolve_local(tmp_path) == f


def test_a_directory_with_one_zip_resolves_to_it(tmp_path):
    f = tmp_path / "dly375.zip"
    f.write_bytes(b"PK\x03\x04")
    assert resolve_local(tmp_path) == f


def test_an_empty_directory_says_so_and_shows_the_fix(tmp_path):
    with pytest.raises(ValueError) as e:
        resolve_local(tmp_path)
    assert "no .csv or .zip" in str(e.value)
    assert "--local" in str(e.value), "the message must show the correction"


def test_an_ambiguous_directory_lists_the_candidates(tmp_path):
    (tmp_path / "dly375.csv").write_text("a")
    (tmp_path / "dly518.csv").write_text("b")
    with pytest.raises(ValueError) as e:
        resolve_local(tmp_path)
    assert "dly375.csv" in str(e.value) and "dly518.csv" in str(e.value)


def test_a_missing_path_is_reported_as_missing_not_as_permissions(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_local(tmp_path / "nope.csv")


# --- --local resolution ----------------------------------------------------

from fetch_met import resolve_local                                # noqa: E402


def test_a_file_path_is_returned_unchanged(tmp_path):
    f = tmp_path / "dly375.csv"
    f.write_text("date,rain\n")
    assert resolve_local(f) == f


def test_a_directory_with_one_csv_resolves_to_it(tmp_path):
    # The real case. Windows raises PermissionError when a directory is opened
    # as a file, which reads as a security problem and is not one.
    f = tmp_path / "dly375.csv"
    f.write_text("date,rain\n")
    assert resolve_local(tmp_path) == f


def test_a_directory_with_one_zip_resolves_to_it(tmp_path):
    f = tmp_path / "dly375.zip"
    f.write_bytes(b"PK\x03\x04")
    assert resolve_local(tmp_path) == f


def test_an_empty_directory_says_so_and_shows_the_fix(tmp_path):
    with pytest.raises(ValueError) as e:
        resolve_local(tmp_path)
    assert "no .csv or .zip" in str(e.value)
    assert "--local" in str(e.value), "the message must show the correction"


def test_an_ambiguous_directory_lists_the_candidates(tmp_path):
    (tmp_path / "dly375.csv").write_text("a")
    (tmp_path / "dly518.csv").write_text("b")
    with pytest.raises(ValueError) as e:
        resolve_local(tmp_path)
    assert "dly375.csv" in str(e.value) and "dly518.csv" in str(e.value)


def test_a_missing_path_is_reported_as_missing_not_as_permissions(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_local(tmp_path / "nope.csv")
