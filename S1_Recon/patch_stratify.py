"""Make stratify.py implement Amendment 1's fit range.

Amendment 1 to PREREGISTRATION_2018.md fixed the fit range as the met-derived
drought window INTERSECTED with peak biomass (DOY >= PEAK_DOY). The code does
not do that: it replaces the limb bounds with the window's own bounds.

With 2018's window (DOY 151-253) that would fit a line from 31 May, roughly
thirty days before peak biomass, through the turning point and down the
senescence limb. A straight line through a maximum is not a senescence rate,
and the poor fit would inflate the standard errors and spend the power the
nine-year baseline was meant to buy.

Two changes, and a third that is only words.

1. INTERSECT rather than replace. The met rule says when the drought ran; the
   limb bounds say when the vegetation signal is monotonic. The fit range is
   where both hold.

2. REPORT the intersection. The operator needs to see the range actually
   fitted, not just the window that was read, or a correct computation carries
   a misleading label - the failure mode behind seven of this project's
   nonconformances.

3. The PRIMARY header hardcodes "1 Jul to 30 Sep" regardless of the window in
   force. Same class of error, caught before it printed anything false.

Usage:
    python patch_stratify.py <path to stratify.py>
"""

from __future__ import annotations

import sys
from pathlib import Path

S1_OLD = '''    lo_doy, hi_doy, window_tag = PEAK_DOY, END_DOY, ""
    if args.window_from:
        w = json.loads(args.window_from.read_text())
        if not w.get("start_doy"):
            print(f"{args.window_from} defines no window; using the full limb")
        else:
            lo_doy, hi_doy = int(w["start_doy"]), int(w["end_doy"])
            window_tag = "_window"
            print(f"drought window from {args.window_from.name}:")
            print(f"  {w['start']} to {w['end']}  (DOY {lo_doy}-{hi_doy}, "
                  f"{hi_doy - lo_doy + 1} days)")
            print(f"  rule: {w.get('method', '?')}")
            print(f"  derived from: {w.get('derived_from', '?')}")
            print(f"  frozen on: {w.get('derived_on', '?')}\\n")
    else:
        print(f"full senescence limb, DOY {lo_doy}-{hi_doy}\\n")
'''

S1_NEW = '''    lo_doy, hi_doy, window_tag = PEAK_DOY, END_DOY, ""
    if args.window_from:
        w = json.loads(args.window_from.read_text())
        if not w.get("start_doy"):
            print(f"{args.window_from} defines no window; using the full limb")
        else:
            win_lo, win_hi = int(w["start_doy"]), int(w["end_doy"])
            # Amendment 1 to the 2018 pre-registration: the fit range is the
            # met-derived window INTERSECTED with the senescence limb, not the
            # window itself. The two rules answer different questions -- the
            # met rule says when the drought ran, the limb bounds say when the
            # vegetation signal is monotonic -- and a slope is only meaningful
            # where both hold. 2018's window opens on DOY 151, a month before
            # peak biomass; fitting a line from there would run it through a
            # maximum and call the result a senescence rate.
            lo_doy, hi_doy = max(win_lo, PEAK_DOY), min(win_hi, END_DOY)
            window_tag = "_window"
            print(f"drought window from {args.window_from.name}:")
            print(f"  {w['start']} to {w['end']}  (DOY {win_lo}-{win_hi}, "
                  f"{win_hi - win_lo + 1} days)")
            print(f"  rule: {w.get('method', '?')}")
            print(f"  derived from: {w.get('derived_from', '?')}")
            print(f"  frozen on: {w.get('derived_on', '?')}")
            if (lo_doy, hi_doy) != (win_lo, win_hi):
                print(f"  intersected with the senescence limb "
                      f"(DOY {PEAK_DOY}-{END_DOY}) per Amendment 1")
            print(f"  FIT RANGE: DOY {lo_doy}-{hi_doy}  "
                  f"({hi_doy - lo_doy + 1} days)\\n")
            if lo_doy > hi_doy:
                raise SystemExit(
                    f"the window (DOY {win_lo}-{win_hi}) does not overlap the "
                    f"senescence limb (DOY {PEAK_DOY}-{END_DOY}); there is "
                    f"nothing to fit")
    else:
        print(f"full senescence limb, DOY {lo_doy}-{hi_doy}\\n")
'''

S2_OLD = '''              f"observable: {METRIC_NAME[args.metric]}\\n"
              f"senescence slope, 1 Jul to 30 Sep, dB per month\\n{'=' * 70}")'''

S2_NEW = '''              f"observable: {METRIC_NAME[args.metric]}\\n"
              f"senescence slope, DOY {lo_doy}-{hi_doy}, dB per month"
              f"\\n{'=' * 70}")'''

REPLACEMENTS = [
    ("S1 intersect the window with the limb", S1_OLD, S1_NEW),
    ("S2 header states the real fit range", S2_OLD, S2_NEW),
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    text = original = path.read_text(encoding="utf-8")

    failures = []
    for label, old, new in REPLACEMENTS:
        n = text.count(old)
        if n != 1:
            failures.append(f"{label}: anchor matched {n} times, expected 1")
            continue
        text = text.replace(old, new, 1)

    if failures:
        print("PATCH NOT APPLIED - file unchanged:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    # The SECONDARY section genuinely fits PEAK_DOY..END_DOY regardless of any
    # window -- it is the single-base-year test that sits outside the
    # pre-registration -- so its "1 Jul to 30 Sep" label is accurate and stays.
    # Exactly one such label should survive.
    n_hard = text.count("1 Jul to 30 Sep")
    if n_hard != 1:
        print(f"PATCH NOT APPLIED - expected exactly 1 hardcoded range label "
              f"(the SECONDARY section), found {n_hard}", file=sys.stderr)
        return 1
    if "senescence slope, DOY {lo_doy}-{hi_doy}" not in text:
        print("PATCH NOT APPLIED - the PRIMARY header does not state its fit "
              "range", file=sys.stderr)
        return 1

    import ast
    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"PATCH NOT APPLIED - result would not parse: {exc}",
              file=sys.stderr)
        return 1

    backup = path.with_suffix(".py.pre-amendment1")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"backup: {backup.name}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name}: {len(REPLACEMENTS)} replacements, parses clean")
    print("\\nfit range is now max(window_start, PEAK_DOY) to min(window_end, END_DOY)")
    print("2018: window DOY 151-253 -> fit range DOY 182-253")
    print("2026: window DOY 183-240 -> fit range DOY 183-240 (unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
