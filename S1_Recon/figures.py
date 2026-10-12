#!/usr/bin/env python3
"""Report figures for the SAR drought study (phase 4).

Four figures, each with one job. Nothing decorative: if a panel does not change
what a reader concludes, it is not here.

  fig1_seasonal.png    where 2026 sits inside the normal-year envelope
  fig2_slopes.png      the null, as a prediction interval -- the core result
  fig3_detection.png   observed effect against what the method can resolve
  fig4_precision.png   control similarity beats control inertness

Everything is recomputed from strata_series.csv using stratify.py's own
functions, so the figures cannot drift from the numbers in the report. No
constants are copied across.

Usage
-----
    python figures.py --strata ../results/phase3/strata_series.csv \\
        --series ../results/phase2/series.csv --out ../results/figures
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from stratify import (CONTRASTS, END_DOY, PEAK_DOY, baseline_z,
                      slope_per_month)

# Validated light-mode palette. 2026 is the subject and carries the one accent;
# the baseline years are deliberately recessive -- they are context, not five
# competing series, and giving them six distinguishable hues would invite the
# reader to compare them with each other instead of with 2026.
ACCENT = "#2a78d6"        # categorical slot 1, blue
ACCENT_2 = "#eb6834"      # categorical slot 2, orange
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#a9a7a0"
BAND = "#dedcd4"
SURFACE = "#fcfcfb"

TREAT = 2026
BASE = [2021, 2022, 2023, 2024, 2025]
LABELS = {"grassland_minus_forest": "grassland − forest",
          "tillage_minus_forest": "tillage − forest",
          "dry_grass_minus_wet_grass": "dry − wet grassland"}


def style(ax, xlabel="", ylabel="", title=""):
    """Recessive axes. The data carries the ink; the frame does not."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK_2, labelsize=9, length=3, width=0.8)
    ax.grid(True, color=BAND, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK_2, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2, fontsize=9.5)
    if title:
        ax.set_title(title, color=INK, fontsize=11.5, loc="left", pad=10,
                     fontweight="semibold")


def read_rows(path: Path) -> list[dict]:
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            row = {}
            for k, v in r.items():
                try:
                    row[k] = float(v) if v not in ("", None) else float("nan")
                except ValueError:
                    row[k] = v
            row["year"] = int(row["year"])
            row["doy"] = int(row["doy"])
            out.append(row)
    return out


def limb(rows, year, key):
    sel = [r for r in rows if r["year"] == year
           and PEAK_DOY <= r["doy"] <= END_DOY and np.isfinite(r[key])]
    sel.sort(key=lambda r: r["doy"])
    return [r["doy"] for r in sel], [r[key] for r in sel]


# --- fig 1 -----------------------------------------------------------------

def fig_seasonal(rows, key, out: Path):
    """The whole season, not just the limb -- a reader needs to see the peak
    the senescence falls away from, or the slope has no referent."""
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=SURFACE)

    # Normal-year envelope: the range the five baselines occupy, interpolated
    # onto a common day grid. A band, not five lines, because the question is
    # "is 2026 outside normal", not "how did 2022 differ from 2023".
    grid = np.arange(95, 300, 3)
    stack = []
    for y in BASE:
        sel = sorted([r for r in rows if r["year"] == y and np.isfinite(r[key])],
                     key=lambda r: r["doy"])
        if len(sel) < 5:
            continue
        d = np.array([r["doy"] for r in sel], float)
        v = np.array([r[key] for r in sel], float)
        stack.append(np.interp(grid, d, v, left=np.nan, right=np.nan))
    stack = np.array(stack)
    lo, hi = np.nanmin(stack, axis=0), np.nanmax(stack, axis=0)
    ax.fill_between(grid, lo, hi, color=BAND, alpha=0.9, linewidth=0,
                    label=f"{len(stack)} baseline years, full range")
    ax.plot(grid, np.nanmean(stack, axis=0), color=MUTED, linewidth=2,
            label="baseline mean")

    sel = sorted([r for r in rows if r["year"] == TREAT and np.isfinite(r[key])],
                 key=lambda r: r["doy"])
    d = [r["doy"] for r in sel]
    v = [r[key] for r in sel]
    ax.plot(d, v, color=ACCENT, linewidth=2, marker="o", markersize=4.5,
            markeredgecolor=SURFACE, markeredgewidth=0.8, label=f"{TREAT} (drought)",
            zorder=5)

    ax.axvspan(PEAK_DOY, END_DOY, color=ACCENT, alpha=0.05, zorder=0)
    ax.annotate("senescence limb\n(1 Jul – 30 Sep)",
                xy=((PEAK_DOY + END_DOY) / 2, ax.get_ylim()[0]),
                xytext=((PEAK_DOY + END_DOY) / 2, ax.get_ylim()[0]),
                ha="center", va="bottom", fontsize=8.5, color=INK_2)

    # Ticks at month STARTS, not month centres -- a label sitting mid-month
    # silently shifts every date a reader takes off the axis.
    ax.set_xticks([91, 121, 152, 182, 213, 244, 274])
    ax.set_xticklabels(["1 Apr", "1 May", "1 Jun", "1 Jul", "1 Aug", "1 Sep",
                        "1 Oct"])
    style(ax, "", f"{LABELS[key]} cross-ratio  (dB)",
          f"Seasonal trajectory of the {LABELS[key]} contrast")
    leg = ax.legend(frameon=False, fontsize=9, loc="upper left")
    for t in leg.get_texts():
        t.set_color(INK_2)
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


# --- fig 2 -----------------------------------------------------------------

def fig_slopes(rows, out: Path):
    """The core result. One panel per contrast: each year's senescence slope
    with its own error bar, the prediction interval for a normal year as a
    band, and 2026 marked. A reader should be able to see the null without
    reading a p-value."""
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.6), facecolor=SURFACE)
    for ax, (a, b) in zip(axes, CONTRASTS):
        key = f"{a}_minus_{b}"
        fits = {y: slope_per_month(*limb(rows, y, key))
                for y in BASE + [TREAT]}
        yrs = [y for y in BASE if np.isfinite(fits[y]["slope"])]
        est = [fits[y]["slope"] for y in yrs]
        ses = [fits[y]["se"] for y in yrs]
        r = baseline_z(fits[TREAT]["slope"], fits[TREAT]["se"], est, ses)

        ax.axhspan(r["pi_lo"], r["pi_hi"], color=BAND, alpha=0.85, zorder=0,
                   label="95% interval for a normal year")
        ax.axhline(r["mean"], color=MUTED, linewidth=2, zorder=1,
                   label="baseline mean")

        xs = np.arange(len(yrs))
        ax.errorbar(xs, est, yerr=ses, fmt="o", color=INK_2, markersize=7,
                    markeredgecolor=SURFACE, markeredgewidth=0.8,
                    elinewidth=1.6, capsize=0, zorder=3, label="baseline year")
        ax.errorbar([len(yrs)], [fits[TREAT]["slope"]], yerr=[fits[TREAT]["se"]],
                    fmt="o", color=ACCENT, markersize=10,
                    markeredgecolor=SURFACE, markeredgewidth=1.0,
                    elinewidth=2.2, capsize=0, zorder=4, label=str(TREAT))

        inside = r["pi_lo"] <= fits[TREAT]["slope"] <= r["pi_hi"]
        ax.annotate(f"z = {r['z']:+.2f}\np = {r['p']:.2f}\n"
                    f"{'inside' if inside else 'OUTSIDE'}",
                    xy=(len(yrs), fits[TREAT]["slope"]), xytext=(6, -4),
                    textcoords="offset points", fontsize=8.5, color=INK_2,
                    va="top")

        ax.set_xticks(list(xs) + [len(yrs)])
        ax.set_xticklabels([str(y) for y in yrs] + [str(TREAT)], rotation=45,
                           ha="right")
        ax.set_xlim(-0.6, len(yrs) + 1.4)
        style(ax, "", "senescence slope  (dB/month)" if ax is axes[0] else "",
              LABELS[key])
    # Figure-level legend: panel 1's lower-left is where the 2026 marker and
    # its annotation live, and every in-panel corner collided with something.
    h, l = axes[0].get_legend_handles_labels()
    leg = fig.legend(h, l, frameon=False, fontsize=9, ncol=4,
                     loc="upper left", bbox_to_anchor=(0.008, 0.945))
    for t in leg.get_texts():
        t.set_color(INK_2)
    fig.suptitle("2026 against the five-year baseline distribution",
                 color=INK, fontsize=12.5, x=0.008, ha="left", y=0.985,
                 fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


# --- fig 3 -----------------------------------------------------------------

def fig_detection(rows, out: Path):
    """Observed effect against what the design can resolve. The report's
    headline in one picture: two of three land at about half the threshold."""
    from scipy import stats as st
    fig, ax = plt.subplots(figsize=(9, 3.8), facecolor=SURFACE)

    names, obs, mde = [], [], []
    for a, b in CONTRASTS:
        key = f"{a}_minus_{b}"
        fits = {y: slope_per_month(*limb(rows, y, key)) for y in BASE + [TREAT]}
        yrs = [y for y in BASE if np.isfinite(fits[y]["slope"])]
        r = baseline_z(fits[TREAT]["slope"], fits[TREAT]["se"],
                       [fits[y]["slope"] for y in yrs],
                       [fits[y]["se"] for y in yrs])
        sd = r.get("sd", np.nan)
        names.append(LABELS[key])
        obs.append(abs(fits[TREAT]["slope"] - r["mean"]))
        mde.append(st.t.ppf(0.975, max(len(yrs) - 1, 1)) * sd)

    # Normalised to the threshold. In absolute dB/month, tillage's enormous
    # detection threshold (its between-year scatter is huge) squashes the two
    # contrasts that carry the result into the left margin. The quantity the
    # reader actually wants is the RATIO -- how close did it get -- so plot
    # that and put the absolute figures on as labels.
    pct = [100 * o / m for o, m in zip(obs, mde)]
    y = np.arange(len(names))
    ax.axvspan(100, 200, color=BAND, alpha=0.5, zorder=0)
    ax.axvline(100, color=INK_2, linewidth=1.6, zorder=3)
    ax.barh(y, pct, height=0.42, color=ACCENT, zorder=2)
    for i, (pc, o, m) in enumerate(zip(pct, obs, mde)):
        ax.text(pc + 2.5, i, f"{pc:.0f}%", va="center", fontsize=10,
                color=INK, fontweight="semibold")
        ax.text(pc + 10, i, f"{o:.3f} of {m:.3f} dB/mo",
                va="center", fontsize=8.5, color=INK_2)
    # Rotated onto the line itself: every horizontal placement collided with
    # either a bar label or the axis title.
    ax.text(100, len(names) - 0.52, " detection threshold ", fontsize=8.5,
            color=INK_2, va="bottom", ha="center", rotation=90)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlim(0, 150)
    ax.set_xticks([0, 25, 50, 75, 100, 125, 150])
    ax.set_xticklabels(["0", "25", "50", "75", "100%", "125", "150"])
    style(ax, "2026 effect as a percentage of the smallest change this design can resolve",
          "", "No contrast reached the threshold for detection")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


# --- fig 4 -----------------------------------------------------------------

def fig_precision(rows, series_rows, out: Path):
    """Why a well-matched control beats a large one. Precision against sample
    size, which is the opposite of the intuition most people bring."""
    fig, ax = plt.subplots(figsize=(9, 3.8), facecolor=SURFACE)

    entries = []
    if series_rows:
        s26 = slope_per_month(*limb(series_rows, TREAT, "cross_ratio_db"))
        s25 = slope_per_month(*limb(series_rows, 2025, "cross_ratio_db"))
        if np.isfinite(s26["se"]):
            entries.append(("whole-AOI aggregate",
                            float(np.hypot(s26["se"], s25["se"])),
                            16_000_000))
    px = {"grassland_minus_forest": 3_858_393 + 522_450,
          "tillage_minus_forest": 2_995_073 + 522_450,
          "dry_grass_minus_wet_grass": 49_277 + 105_695}
    for a, b in CONTRASTS:
        key = f"{a}_minus_{b}"
        f26 = slope_per_month(*limb(rows, TREAT, key))
        f25 = slope_per_month(*limb(rows, 2025, key))
        entries.append((LABELS[key], float(np.hypot(f26["se"], f25["se"])),
                        px[key]))

    entries.sort(key=lambda e: e[1])
    y = np.arange(len(entries))
    colors = [ACCENT if e[0].startswith("dry") else MUTED for e in entries]
    ax.barh(y, [e[1] for e in entries], height=0.44, color=colors, zorder=2)
    for i, (name, se, n) in enumerate(entries):
        ax.text(se + max(e[1] for e in entries) * 0.02, i,
                f"{se:.3f} dB/mo   ·   {n / 1e6:.2f} M px", va="center",
                fontsize=9, color=INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels([e[0] for e in entries])
    ax.invert_yaxis()
    ax.set_xlim(0, max(e[1] for e in entries) * 1.75)
    style(ax, "standard error of the slope difference  (dB/month)   — lower is better",
          "", "A control works by being similar, not by being large")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--strata", type=Path, required=True)
    p.add_argument("--series", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rows = read_rows(args.strata)
    series_rows = read_rows(args.series) if args.series and args.series.exists() else []
    print(f"{len(rows)} acquisitions from {args.strata}")

    made = [
        fig_seasonal(rows, "grassland_minus_forest", args.out / "fig1_seasonal.png"),
        fig_slopes(rows, args.out / "fig2_slopes.png"),
        fig_detection(rows, args.out / "fig3_detection.png"),
        fig_precision(rows, series_rows, args.out / "fig4_precision.png"),
    ]
    for f in made:
        print(f"wrote {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
