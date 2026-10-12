"""Tests for ipf_check.py -- the IPF processor-baseline audit."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import ipf_check as ic


# --------------------------------------------------------------------------
# parse_version
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("ESA SENTINEL-1 IPF 002.84", ("2.84", 2.84)),
    ("ESA SENTINEL-1 IPF 003.10", ("3.10", 3.10)),
    ("Sentinel-1 IPF 2.90", ("2.90", 2.90)),
    ("ESA SENTINEL-1 IPF 003.71", ("3.71", 3.71)),
])
def test_parse_version_reads_real_identifier_strings(text, expected):
    assert ic.parse_version(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "unknown", "ESA SENTINEL-1", None])
def test_parse_version_returns_none_rather_than_guessing(text):
    assert ic.parse_version(text) == (None, None)


def test_parse_version_strips_leading_zeros_but_keeps_minor_width():
    """002.84 and 2.84 are the same baseline; the minor part is not a number
    to be normalised -- 002.9 and 002.90 are different strings in the wild."""
    assert ic.parse_version("IPF 002.84")[0] == "2.84"
    assert ic.parse_version("IPF 002.07")[0] == "2.07"


def test_parse_version_numeric_ordering_is_usable():
    """Epoch comparison is done numerically, so 2.90 must sort below 3.10."""
    _, a = ic.parse_version("IPF 002.90")
    _, b = ic.parse_version("IPF 003.10")
    assert a < b


def test_stripping_the_major_zeros_does_not_break_numeric_comparison():
    """The display string drops leading zeros ('002.84' -> '2.84'), so it can
    no longer be sorted as text once a major version reaches double digits.
    Every comparison in this module must therefore use ipf_numeric."""
    hi, hi_n = ic.parse_version("IPF 010.01")
    lo, lo_n = ic.parse_version("IPF 002.84")
    assert hi_n > lo_n          # numeric: correct
    assert not (hi > lo)        # text: wrong, which is why we don't use it


# --------------------------------------------------------------------------
# scene_id
# --------------------------------------------------------------------------

def test_scene_id_splits_the_project_naming_convention():
    assert ic.scene_id("20260717_S1D") == ("20260717", "S1D")
    assert ic.scene_id("20180702_S1B") == ("20180702", "S1B")


def test_scene_id_tolerates_extra_parts():
    assert ic.scene_id("20260717_S1D_extra") == ("20260717", "S1D")


def test_scene_id_does_not_crash_on_an_unexpected_name():
    assert ic.scene_id("nonsense") == ("nonsense", "")


# --------------------------------------------------------------------------
# crosses_noise_epoch
# --------------------------------------------------------------------------

def test_single_version_crosses_nothing():
    assert ic.crosses_noise_epoch({2.84}) == []


def test_empty_crosses_nothing():
    assert ic.crosses_noise_epoch(set()) == []


def test_versions_either_side_of_2_90_are_flagged():
    flagged = ic.crosses_noise_epoch({2.84, 3.10})
    assert len(flagged) == 2  # straddles both 2.90 and 3.10


def test_versions_below_the_first_epoch_are_not_flagged():
    assert ic.crosses_noise_epoch({2.70, 2.84}) == []


def test_versions_above_the_last_epoch_are_not_flagged():
    assert ic.crosses_noise_epoch({3.31, 3.71}) == []


def test_the_epoch_boundary_is_inclusive_on_the_upper_side():
    """A series running 2.84 -> 2.90 did change noise vectors at the top end."""
    assert len(ic.crosses_noise_epoch({2.84, 2.90})) == 1


def test_a_series_starting_exactly_at_the_epoch_does_not_straddle_it():
    assert ic.crosses_noise_epoch({2.90, 3.00}) == []


# --------------------------------------------------------------------------
# summarise
# --------------------------------------------------------------------------

def rows(*specs):
    """Build rows the way scan() would. specs are (scene, ipf) pairs."""
    out = []
    for scene, ipf in specs:
        date, platform = ic.scene_id(scene)
        text, numeric = ic.parse_version(f"IPF {ipf}") if ipf else (None, None)
        out.append({"scene": scene, "date": date, "platform": platform,
                    "ipf": text or "", "ipf_numeric": numeric,
                    "identifier": f"IPF {ipf}" if ipf else ""})
    return out


def test_summarise_groups_versions_by_year():
    s = ic.summarise(rows(
        ("20180702_S1A", "002.84"),
        ("20180708_S1B", "002.84"),
        ("20260717_S1D", "003.71"),
    ))
    assert s["by_year"] == {"2018": [2.84], "2026": [3.71]}


def test_summarise_counts_distinct_versions_across_the_whole_series():
    s = ic.summarise(rows(
        ("20180702_S1A", "002.84"),
        ("20210702_S1A", "003.31"),
        ("20260717_S1D", "003.71"),
    ))
    assert s["n_versions"] == 3


def test_summarise_flags_a_year_with_mixed_versions():
    s = ic.summarise(rows(
        ("20180602_S1A", "002.84"),
        ("20180902_S1A", "002.90"),
    ))
    assert s["within_year_mixed"] == ["2018"]


def test_summarise_does_not_flag_a_year_that_is_internally_consistent():
    s = ic.summarise(rows(
        ("20180602_S1A", "002.84"),
        ("20180902_S1A", "002.84"),
        ("20260717_S1D", "003.71"),
    ))
    assert s["within_year_mixed"] == []


def test_summarise_reports_the_real_2018_vs_2026_case():
    """The actual T1 concern: 2018 on an early baseline, 2026 on a late one."""
    s = ic.summarise(rows(
        ("20180702_S1A", "002.84"),
        ("20180708_S1B", "002.84"),
        ("20260717_S1D", "003.71"),
    ))
    assert s["n_versions"] == 2
    assert len(s["series_epochs"]) == 2
    assert s["within_year_mixed"] == []


def test_summarise_collects_unreadable_versions_separately():
    s = ic.summarise(rows(
        ("20180702_S1A", "002.84"),
        ("20180708_S1B", None),
    ))
    assert s["unknown"] == ["20180708_S1B"]
    assert s["n_versions"] == 1


def test_unknown_versions_do_not_enter_the_year_groups():
    """An unreadable version must not silently become a year with no versions."""
    s = ic.summarise(rows(("20180708_S1B", None)))
    assert s["by_year"] == {}
    assert s["unknown"] == ["20180708_S1B"]


def test_summarise_lists_scenes_under_each_version():
    s = ic.summarise(rows(
        ("20180702_S1A", "002.84"),
        ("20180708_S1B", "002.84"),
        ("20260717_S1D", "003.71"),
    ))
    assert s["by_version"]["2.84"] == ["20180702_S1A", "20180708_S1B"]
    assert s["by_version"]["3.71"] == ["20260717_S1D"]


# --------------------------------------------------------------------------
# read_identifier -- against a .dim-shaped header
# --------------------------------------------------------------------------

def write_dim(path: Path, identifier: str | None) -> Path:
    root = ET.Element("Dimap_Document")
    src = ET.SubElement(root, "Dataset_Sources")
    meta = ET.SubElement(src, "MDElem", {"name": "metadata"})
    abstract = ET.SubElement(meta, "MDElem", {"name": "Abstracted_Metadata"})
    ET.SubElement(abstract, "MDATTR", {"name": "PRODUCT"}).text = "S1A_IW_GRDH"
    if identifier is not None:
        el = ET.SubElement(abstract, "MDATTR", {"name": ic.ATTR})
        el.text = identifier
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def test_read_identifier_finds_the_attribute_at_depth(tmp_path):
    dim = write_dim(tmp_path / "20180702_S1A.dim", "ESA SENTINEL-1 IPF 002.84")
    assert ic.read_identifier(dim) == "ESA SENTINEL-1 IPF 002.84"


def test_read_identifier_returns_empty_when_the_attribute_is_absent(tmp_path):
    dim = write_dim(tmp_path / "20180702_S1A.dim", None)
    assert ic.read_identifier(dim) == ""


def test_read_identifier_raises_a_named_error_on_a_corrupt_header(tmp_path):
    bad = tmp_path / "broken.dim"
    bad.write_text("<Dimap_Document><unclosed>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="broken.dim"):
        ic.read_identifier(bad)


def test_read_identifier_strips_surrounding_whitespace(tmp_path):
    dim = write_dim(tmp_path / "s.dim", "  ESA SENTINEL-1 IPF 002.84  ")
    assert ic.read_identifier(dim) == "ESA SENTINEL-1 IPF 002.84"


# --------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------

def test_scan_reads_every_dim_in_sorted_order(tmp_path):
    write_dim(tmp_path / "20260717_S1D.dim", "IPF 003.71")
    write_dim(tmp_path / "20180702_S1A.dim", "IPF 002.84")
    found = ic.scan(tmp_path)
    assert [r["scene"] for r in found] == ["20180702_S1A", "20260717_S1D"]
    assert [r["ipf"] for r in found] == ["2.84", "3.71"]


def test_scan_ignores_non_dim_files(tmp_path):
    write_dim(tmp_path / "20180702_S1A.dim", "IPF 002.84")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "20180702_S1A.data").mkdir()
    assert len(ic.scan(tmp_path)) == 1


def test_scan_survives_one_corrupt_header_among_good_ones(tmp_path, capsys):
    """One bad file must not abort the audit of 150 good ones."""
    write_dim(tmp_path / "20180702_S1A.dim", "IPF 002.84")
    (tmp_path / "20180708_S1B.dim").write_text("<broken", encoding="utf-8")
    found = ic.scan(tmp_path)
    assert len(found) == 2
    assert found[1]["ipf"] == ""
    assert "unreadable" in capsys.readouterr().err


def test_scan_returns_empty_for_a_directory_with_no_dims(tmp_path):
    assert ic.scan(tmp_path) == []
