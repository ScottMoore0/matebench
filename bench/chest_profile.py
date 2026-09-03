#!/usr/bin/env python3
"""Does ChestUCI supply fresh positions matching the pathological profile?

The learned-ordering positive (W4096 gate28, +0.0230 AUC, |d|/se 2.56) is the
only arm in this project's ordering work ever to clear its harness's visibility
threshold, and the harness insists such results be replicated on fresh positions.
That replication returned ZERO: the profile - d>=14, at least 28 legal moves, at
most 10% of them checks - matches only 138 positions in matetrack, and the
original run consumed essentially all of them.

ChestUCI.epd is an INDEPENDENT corpus of 6728 problems shipped with Chest, with
953 at d>=14. If enough of those match the profile, the replication becomes
possible on positions that share no provenance with the selecting run - which is
a stronger test than a split-half of the original pool would have been.

Writes the matches in the harness's own EPD form so trialsgated can consume them
directly, and reports the count so the design can be sized before anything is
run.
"""
import argparse
import re
from pathlib import Path

import chess
import config  # paths: see bench/config.py

SRC = config.corpus("chestuci.epd")
BM = re.compile(r"\bbm\s+#(\d+)")

ap = argparse.ArgumentParser()
ap.add_argument("--min-depth", type=int, default=14)
ap.add_argument("--min-legal", type=int, default=28)
ap.add_argument("--max-check-frac", type=float, default=0.10)
ap.add_argument("--out", default=str(Path.home() / "mh" / "chest_wide.epd"))
a = ap.parse_args()

seen, kept, scanned, deep = set(), [], 0, 0
for line in SRC.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("%"):
        continue
    m = BM.search(line)
    if not m:
        continue
    d = int(m.group(1))
    scanned += 1
    if d < a.min_depth:
        continue
    deep += 1
    fen = line.split(" bm ")[0].strip()
    try:
        b = chess.Board(fen)
    except Exception:
        continue
    moves = list(b.legal_moves)
    if len(moves) < a.min_legal:
        continue
    checks = sum(1 for mv in moves if b.gives_check(mv))
    if checks / max(1, len(moves)) > a.max_check_frac:
        continue
    key = " ".join(fen.split()[:4])
    if key in seen:
        continue
    seen.add(key)
    kept.append((key, d))

print("  scanned %d problems, %d at d>=%d" % (scanned, deep, a.min_depth))
print("  matching the full profile (>=%d legal, <=%.0f%% checks): %d"
      % (a.min_legal, 100 * a.max_check_frac, len(kept)))
Path(a.out).write_text(
    "".join("%s bm #%d;\n" % (f, d) for f, d in kept), encoding="utf-8")
print("  wrote %s" % a.out)
print()
if len(kept) >= 120:
    print("  -> ENOUGH for a real replication (matetrack had 138 total, all used).")
    print("     These share no provenance with the selecting run, which is a")
    print("     stronger test than a split-half of the original pool.")
elif len(kept) >= 40:
    print("  -> %d positions: enough for a reduced-power replication only." % len(kept))
    print("     Size the design against |d|/se 2.56 before believing a null.")
else:
    print("  -> TOO FEW (%d). The profile is rare in this corpus too, and the" % len(kept))
    print("     ordering positive stays unverifiable.")
print("\n=== CHEST PROFILE ENDED ===")
