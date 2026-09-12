#!/usr/bin/env python3
"""Position pools: the sampling every measurement script draws from.

One function, `by_depth`, because that is what the harness uses. Given a depth
range it returns positions from a checksummed corpus, optionally capped per
depth and drawn under a named seed.

THE SEED IS THE REPRODUCIBILITY CONTRACT. A result log is only re-runnable if
the same (corpus, depth, per_depth, seed) yields the same positions, so the
draw is defined here and nowhere else:

  * positions are bucketed by depth in corpus order;
  * each depth gets its OWN generator, `Random("<seed>:<depth>")`, so adding or
    removing a depth from a run cannot change what another depth drew;
  * the shuffle is applied to the whole bucket and the cap taken afterwards.

Taking the first N of a depth range instead would be silently biased: the
corpora are SORTED by depth, so the first N of d4-d40 are all d4-d8. That is a
real defect this shape exists to prevent, not a hypothetical one.

The corpus is `matetrack.epd` by default, whose sha256 is recorded in
corpora/CHECKSUMS.json by `fetch_corpora.py`. Override with the environment
variable MATEBENCH_POOL_CORPUS, and record the checksum of whatever replaces
it, or the seed contract above buys nothing.

Deliberately NOT cached. An earlier version of this module memoised each pool
to disk under a key built from the filter parameters ALONE -- not the corpus --
so a changed corpus silently returned the previous corpus's positions. Parsing
the corpus takes milliseconds; a stale pool costs a wrong result log that looks
right. The corpus checksum is the thing that makes a pool reproducible, and it
is checked by `matebench verify-corpora`, not by a cache key.
"""
import os
import random
import re
from pathlib import Path

import config

# A corpus line is "<fen4> ... bm #N;". N is negative in matetrack when the
# side to move is the one being mated; the pool is keyed on distance, so the
# sign is dropped here and the stipulation is the caller's business.
PAT = re.compile(r"^(.*?)\s+bm\s+#(-?\d+)")

POOL_CORPUS = os.environ.get("MATEBENCH_POOL_CORPUS", "matetrack.epd")


def corpus_path():
    return Path(config.corpus(POOL_CORPUS))


def entries(path=None):
    """(fen4, depth) for every stipulated line, in corpus order."""
    src = Path(path) if path else corpus_path()
    if not src.exists():
        raise SystemExit(
            "pool corpus not found: %s\n"
            "  fetch it first:  python bench/matebench.py fetch %s\n"
            "  or point MATEBENCH_POOL_CORPUS at another file in %s"
            % (src, Path(POOL_CORPUS).stem, config.CORPORA))
    # utf-8-sig: the published corpora carry a byte order mark often enough
    # that stripping it here is cheaper than discovering one position short.
    for line in src.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = PAT.match(line.strip())
        if m:
            yield m.group(1).strip(), abs(int(m.group(2)))


def by_depth(lo, hi, per_depth=0, limit=0, seed=None):
    """Positions with lo <= mate depth <= hi.

    per_depth caps each depth separately. seed names the draw; without one the
    positions come back in corpus order, which is biased by depth and kept only
    for a caller that genuinely wants "the first N as they appear".
    """
    if seed is None:
        per, out = {}, []
        for fen, d in entries():
            if not (lo <= d <= hi):
                continue
            if per_depth:
                per.setdefault(d, 0)
                if per[d] >= per_depth:
                    continue
                per[d] += 1
            out.append({"fen4": fen, "mate": d})
            if limit and len(out) >= limit and not per_depth:
                break
        return _with_ids(out)

    buckets = {}
    for fen, d in entries():
        if lo <= d <= hi:
            buckets.setdefault(d, []).append(fen)
    out = []
    for d in sorted(buckets):
        fens = buckets[d]
        random.Random("%s:%d" % (seed, d)).shuffle(fens)
        take = fens[:per_depth] if per_depth else fens
        out += [{"fen4": f, "mate": d} for f in take]
        if limit and len(out) >= limit:
            out = out[:limit]
            break
    return _with_ids(out)


def _with_ids(rows):
    # Ids are positional within THIS call, so a slice of a pool is independent
    # of how the pool was built.
    return [dict(r, _id="p%d" % i) for i, r in enumerate(rows)]


if __name__ == "__main__":
    src = corpus_path()
    total = sum(1 for _ in entries())
    print("corpus: %s" % src)
    print("  stipulated positions: %d" % total)
    for lo, hi in ((8, 8), (12, 12), (16, 16)):
        rows = by_depth(lo, hi, per_depth=12, seed="demo")
        print("  d%-3d seed=demo per_depth=12 -> %d positions" % (lo, len(rows)))
    a = [r["fen4"] for r in by_depth(10, 14, per_depth=5, seed="x")]
    b = [r["fen4"] for r in by_depth(10, 14, per_depth=5, seed="x")]
    assert a == b, "same seed must give the same draw"
    c = [r["fen4"] for r in by_depth(10, 14, per_depth=5, seed="y")]
    assert a != c, "a different seed must give a different draw"
    print("  seeded draw is reproducible, and seed-dependent")
