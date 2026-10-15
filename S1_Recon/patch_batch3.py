"""Make the downloader survive CDSE throttling.

Applies on top of patch_batch.py and patch_batch2.py.

Observed on the 2016-2020 run: a ConnectionResetError, then repeated
ConnectTimeout to catalogue.dataspace.copernicus.eu. A connect timeout is the
TCP handshake not completing, which is refusal rather than slowness. CDSE
limits concurrent downloads per user and monthly transfer volume; this run uses
one sequential stream and is far inside both, so the cause is transient
server-side refusal, not a quota that has been exhausted.

Three things were wrong with how the downloader handled it.

1. The backoff gave up after 15 seconds (3 attempts, 5s then 10s). Throttling
   clears on a scale of minutes.
2. A 120-second CONNECT timeout meant each doomed attempt burned two minutes
   discovering what a refused handshake reports in a few seconds.
3. After a job failed entirely the loop went straight to the next product,
   so one throttle event cascaded into consecutive failures.

Nothing is lost to a failed download: the manifest records it, `already_done`
counts only verified scenes, and the next run retries it.

Usage:
    python patch_batch3.py <path to batch_process.py>
"""

from __future__ import annotations

import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Q1  retry and cooldown constants
# --------------------------------------------------------------------------

Q1_OLD = '''PREFETCH = 1          # raw products downloaded ahead of the processor
MIN_FREE_GB = 12.0    # refuse to start a download below this
'''

Q1_NEW = '''PREFETCH = 1          # raw products downloaded ahead of the processor
MIN_FREE_GB = 12.0    # refuse to start a download below this

# Retry policy, sized for CDSE throttling rather than for a dropped packet.
# 30s, 60s, 120s, 240s, 480s between six attempts: about 15 minutes of patience
# before a product is given up on, against the 15 seconds that preceded it.
MAX_RETRIES = 6
RETRY_BASE_S = 30.0

# Separate connect and read timeouts. A throttled host refuses the handshake,
# which a 30-second connect timeout discovers four times faster than the 120
# seconds that applied to both phases before. The read timeout stays generous
# because a 1.7 GB product legitimately takes a while between chunks.
CONNECT_TIMEOUT_S = 30.0
READ_TIMEOUT_S = 300.0

# After a product is given up on, wait before starting the next one. Charging
# straight into the next download is what turned one refusal into a run of
# consecutive failures.
THROTTLE_COOLDOWN_S = 900.0
'''

# --------------------------------------------------------------------------
# Q2  download_product: longer backoff, split timeouts, readable messages
# --------------------------------------------------------------------------

Q2_OLD = '''def download_product(cdse: Cdse, product_id: str, dest: Path,
                     max_retries: int = 3) -> float:'''

Q2_NEW = '''def download_product(cdse: Cdse, product_id: str, dest: Path,
                     max_retries: int = MAX_RETRIES) -> float:'''

Q2B_OLD = '''            r = cdse.s.get(url, headers=headers, stream=True,
                           allow_redirects=False, timeout=120)
            hops = 0
            while r.status_code in (301, 302, 303, 307, 308) and hops < 10:
                nxt = r.headers["Location"]
                r.close()
                r = cdse.s.get(nxt, headers=headers, stream=True,
                               allow_redirects=False, timeout=120)
                hops += 1'''

Q2B_NEW = '''            timeout = (CONNECT_TIMEOUT_S, READ_TIMEOUT_S)
            r = cdse.s.get(url, headers=headers, stream=True,
                           allow_redirects=False, timeout=timeout)
            hops = 0
            while r.status_code in (301, 302, 303, 307, 308) and hops < 10:
                nxt = r.headers["Location"]
                r.close()
                r = cdse.s.get(nxt, headers=headers, stream=True,
                               allow_redirects=False, timeout=timeout)
                hops += 1'''

Q2C_OLD = '''            wait = 5 * 2 ** attempt
            print(f"    download retry {attempt + 1}/{max_retries} in {wait}s ({exc})",
                  file=sys.stderr)
            time.sleep(wait)'''

Q2C_NEW = '''            wait = RETRY_BASE_S * 2 ** attempt
            # One line per retry. The full urllib3 message runs to several
            # hundred characters and buries the batch's own output.
            why = " ".join(str(exc).split())[:110]
            print(f"    retry {attempt + 1}/{max_retries} in {wait:.0f}s — {why}",
                  file=sys.stderr)
            time.sleep(wait)'''

# --------------------------------------------------------------------------
# Q3  downloader: pause after a failure instead of charging on
# --------------------------------------------------------------------------

Q3_OLD = '''def downloader(jobs: Sequence[Job], raw_dir: Path, q: "queue.Queue",
               cdse: Cdse, stop: threading.Event) -> None:
    """Producer: keeps PREFETCH raw products ready for the processor."""'''

Q3_NEW = '''def downloader(jobs: Sequence[Job], raw_dir: Path, q: "queue.Queue",
               cdse: Cdse, stop: threading.Event,
               cooldown_s: float = THROTTLE_COOLDOWN_S) -> None:
    """Producer: keeps PREFETCH raw products ready for the processor.

    A product that exhausts its retries is reported and the queue continues,
    but only after `cooldown_s`. The failure is already recorded in the
    manifest and the next run will retry it, so waiting costs nothing except
    time — whereas not waiting means the next product meets the same refusal.
    """'''

Q3B_OLD = '''        except Exception as exc:                  # noqa: BLE001
            q.put((job, None, 0.0, exc))
    q.put(None)                                   # sentinel'''

Q3B_NEW = '''        except Exception as exc:                  # noqa: BLE001
            q.put((job, None, 0.0, exc))
            if cooldown_s > 0 and job is not jobs[-1]:
                print(f"    pausing {cooldown_s / 60:.0f} min before the next "
                      f"product", file=sys.stderr)
                stop.wait(cooldown_s)             # interruptible by Ctrl-C
    q.put(None)                                   # sentinel'''

# --------------------------------------------------------------------------
# Q4  CLI flag, and pass it through
# --------------------------------------------------------------------------

Q4_OLD = '''    p.add_argument("--dry-run", action="store_true")'''

Q4_NEW = '''    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--cooldown", type=float, default=THROTTLE_COOLDOWN_S,
                   metavar="SECONDS",
                   help="pause after a product is given up on, so one refusal "
                        "from the archive does not cascade into a run of them "
                        f"(default {THROTTLE_COOLDOWN_S:.0f}; 0 disables)")'''

Q5_OLD = '''    t = threading.Thread(target=downloader, args=(todo, args.raw, q, cdse, stop),
                         daemon=True)'''

Q5_NEW = '''    t = threading.Thread(target=downloader,
                         args=(todo, args.raw, q, cdse, stop, args.cooldown),
                         daemon=True)'''

REPLACEMENTS = [
    ("Q1 constants", Q1_OLD, Q1_NEW),
    ("Q2 retry count", Q2_OLD, Q2_NEW),
    ("Q2b split timeouts", Q2B_OLD, Q2B_NEW),
    ("Q2c backoff", Q2C_OLD, Q2C_NEW),
    ("Q3 downloader docstring", Q3_OLD, Q3_NEW),
    ("Q3b cooldown", Q3B_OLD, Q3B_NEW),
    ("Q4 CLI flag", Q4_OLD, Q4_NEW),
    ("Q5 thread args", Q5_OLD, Q5_NEW),
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
        print("PATCH NOT APPLIED — file unchanged:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print("\nThis applies on top of patch_batch.py and patch_batch2.py.",
              file=sys.stderr)
        return 1

    import ast
    try:
        ast.parse(text)
    except SyntaxError as exc:
        print(f"PATCH NOT APPLIED — result would not parse: {exc}", file=sys.stderr)
        return 1

    backup = path.with_suffix(".py.pre-backoff")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"backup: {backup.name}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.name}: {len(REPLACEMENTS)} replacements, parses clean")
    print("\nretry schedule is now 30s, 60s, 120s, 240s, 480s over 6 attempts")
    print("cooldown after a given-up product: 15 min (--cooldown 0 disables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
