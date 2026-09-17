#!/usr/bin/env python3
"""Split a corpus into a development set and a held-out set by salted hash.

The split is a function of (salt, position) and nothing else, so anyone who
knows the salt can reproduce it exactly, and nobody who does not can predict
it. The round's salt is committed to in advance by publishing its sha256, and
disclosed when the round closes; see docs/HELDOUT.md.

    python bench/heldout.py corpora/chestuci.epd --salt <round salt>
    python bench/heldout.py corpora/chestuci.epd --salt <round salt> --fraction 0.25 --out-dir rounds/2026-10
    python bench/heldout.py corpora/generated.epd --salt-parts <maintainer secret> <submitter secret>

With `--salt-parts`, the salt is sha256 of the parts joined by newlines, so a
round whose maintainer is also a submitter can still be run: each party commits
to sha256 of its own part before the pool exists, every part is published at
close, and no party can steer the split alone (CONTRIBUTING.md).

Writes <stem>.dev.epd and <stem>.heldout.epd and prints the per-band counts of
each, so the held-out set's depth profile is on record before any engine runs.
"""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path
import re

BM = re.compile(r"(?:bm[ ]+#|dm[ ]+)([0-9]+)")
BANDS = [(1, 7, "d1-7"), (8, 12, "d8-12"), (13, 17, "d13-17"), (18, 21, "d18-21"),
         (22, 25, "d22-25"), (26, 30, "d26-30"), (31, 999, "d31+")]


def band(n):
    for lo, hi, name in BANDS:
        if lo <= n <= hi:
            return name
    return "?"


def fen_key(line):
    # the first four EPD fields identify the position; opcodes and comments do not
    return " ".join(line.split()[:4])


def position_id(line):
    # Names a position without revealing it. Results on a corpus that may not be
    # redistributed (ChestUCI) publish this instead of the FEN; anyone holding the
    # corpus can map it back, and nobody else can.
    return hashlib.sha256(fen_key(line).encode("utf-8")).hexdigest()[:16]


def salt_from_parts(parts):
    """One salt from several committed parts, in the order given."""
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def is_heldout(salt, line, fraction):
    h = hashlib.sha256((salt + "|" + fen_key(line)).encode("utf-8")).digest()
    u = int.from_bytes(h[:8], "big") / float(1 << 64)
    return u < fraction


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("epd")
    ap.add_argument("--salt", default="", help="the round's secret salt (commit sha256(salt) first)")
    ap.add_argument("--salt-parts", nargs="+", default=[], metavar="PART",
                    help="one part per party, in the order the round's OPEN.md lists them; the salt is "
                         "sha256 of the parts joined by newlines")
    ap.add_argument("--fraction", type=float, default=0.2, help="held-out share (default 0.2)")
    ap.add_argument("--out-dir", default="", help="where to write the two files (default: beside the input)")
    ap.add_argument("--ids", action="store_true",
                    help="also write <stem>.heldout.ids: position id, band and stated mate length for each "
                         "held-out position, and nothing that reveals the position itself")
    a = ap.parse_args()
    if bool(a.salt) == bool(a.salt_parts):
        sys.exit("give either --salt or --salt-parts, not both")
    if a.salt_parts:
        a.salt = salt_from_parts(a.salt_parts)
        print("  salt from %d parts: sha256 %s" % (len(a.salt_parts), hashlib.sha256(
            a.salt.encode("utf-8")).hexdigest()))
    if not (0 < a.fraction < 1):
        sys.exit("--fraction must be strictly between 0 and 1")
    src = Path(a.epd)
    rows = [l for l in src.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip() and not l.startswith("%")]
    dev, held = [], []
    for l in rows:
        (held if is_heldout(a.salt, l, a.fraction) else dev).append(l)
    out_dir = Path(a.out_dir) if a.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    for name, part in (("dev", dev), ("heldout", held)):
        p = out_dir / ("%s.%s.epd" % (stem, name))
        p.write_text(chr(10).join(part) + chr(10), encoding="utf-8")
    if a.ids:
        p = out_dir / ("%s.heldout.ids" % stem)
        ids = []
        for l in held:
            m = BM.search(l)
            n = int(m.group(1)) if m else None
            ids.append("%s %s %s" % (position_id(l), band(n) if n is not None else "?", n if n is not None else "?"))
        p.write_text(chr(10).join(ids) + chr(10), encoding="utf-8")
        print("wrote %d position ids to %s" % (len(ids), p))
    commit = hashlib.sha256(a.salt.encode("utf-8")).hexdigest()
    print("salt commitment sha256(salt) = %s" % commit)
    print("%s: %d positions -> dev %d, held-out %d (fraction %.2f)" % (src.name, len(rows), len(dev), len(held), a.fraction))
    cd, ch = Counter(), Counter()
    for l in dev:
        m = BM.search(l)
        cd[band(int(m.group(1))) if m else "?"] += 1
    for l in held:
        m = BM.search(l)
        ch[band(int(m.group(1))) if m else "?"] += 1
    print("  %-8s %6s %8s" % ("band", "dev", "held-out"))
    for _, _, name in BANDS:
        if cd[name] or ch[name]:
            print("  %-8s %6d %8d" % (name, cd[name], ch[name]))
    if cd["?"] or ch["?"]:
        print("  %-8s %6d %8d   (no bm #N / dm N opcode)" % ("?", cd["?"], ch["?"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
