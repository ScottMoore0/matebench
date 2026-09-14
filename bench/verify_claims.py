#!/usr/bin/env python3
"""Re-prove the mate claims behind a paired vs_stockfish.py comparison.

vs_stockfish.py counts a position as solved when an engine reports
`score mate N` with 0 < N <= the stated length. That is a claim, not a proof.
Stockfish-family engines rarely claim a mate that is not there, but Huntsman is
recorded in REFERENCE.md as over-claiming, so a comparison against it has to
check what it claims before the counts mean anything.

A paired result rests on the discordant positions, so every claim only one of
the two arms made is re-proved by MateProver (`--direct-depth` at the claimed
length, `--no-portfolio`, node-limited, deterministic). A seeded sample of the
claims both arms made is re-proved as well, to estimate how often a claim is
wrong where the two engines agree.

Three outcomes, never two, plus a fourth for a broken run:
  verified     MateProver proves a mate within the claimed length
  refuted      MateProver proves there is none within the claimed length
  unconfirmed  the node budget ran out first; that is not the same as false
  error        MateProver printed no result line; counted as none of the above

The paired result is then recomputed on verified claims only.
"""
import argparse
import json
import random
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

import config  # paths: see bench/config.py

BM = re.compile(r"\bbm\s+#(\d+)")
DM = re.compile(r"; dm (\d+)")
BANDS = [(10, 13), (14, 17), (18, 21), (22, 25), (26, 30), (31, 999)]


def sign_p(w, l):
    n = w + l
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0


def band_name(n):
    for lo, hi in BANDS:
        if lo <= n <= hi:
            return "d%d-%s" % (lo, hi if hi < 999 else "+")
    return "?"


def prove(fen, claim, nodes):
    out = subprocess.run(
        [config.engine("mateprover"), "-z", str(claim), "--direct-depth", "--no-portfolio",
         "--threads", "1", "--node-limit", str(nodes), "-"],
        input="%s bm #%d;\n" % (fen, claim), capture_output=True, text=True, errors="replace").stdout
    if "; acn " not in out:
        return "error"          # no result line: a crash must not read as a refutation
    m = DM.search(out)
    if m and 0 < int(m.group(1)) <= claim:
        return "verified"
    if "timeout" in out:
        return "unconfirmed"
    return "refuted"            # a completed search that found no mate within the claim


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--a", required=True, help="first arm, e.g. mh19-null")
ap.add_argument("--b", required=True, help="second arm, e.g. huntsman")
ap.add_argument("--corpus", default="chestuci.epd")
ap.add_argument("--min-depth", type=int, default=10)
ap.add_argument("--max-depth", type=int, default=999)
ap.add_argument("--budget", default="10000000", help="the vs_stockfish budget key: node count, or tNNNN")
ap.add_argument("--verify-nodes", type=int, default=20_000_000)
ap.add_argument("--shared-sample", type=int, default=100)
ap.add_argument("--seed", default="verify-claims")
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--state", default=config.results("verify_claims_state.json"))
a = ap.parse_args()

runs = json.loads(Path(config.results("vs_stockfish_state.json")).read_text())
cases = []
for line in config.corpus(a.corpus).read_text(encoding="utf-8", errors="replace").splitlines():
    m = BM.search(line)
    if m and not line.startswith("%") and a.min_depth <= int(m.group(1)) <= a.max_depth:
        cases.append((" ".join(line.split(" bm ")[0].split()[:4]), int(m.group(1))))
cases = [(f, d) for f, d in cases
         if "%s|%s|%s" % (f, a.a, a.budget) in runs and "%s|%s|%s" % (f, a.b, a.budget) in runs]
claim = lambda f, arm: runs["%s|%s|%s" % (f, arm, a.budget)].get("dm")

only_a = [(f, d) for f, d in cases if claim(f, a.a) and not claim(f, a.b)]
only_b = [(f, d) for f, d in cases if claim(f, a.b) and not claim(f, a.a)]
shared = [(f, d) for f, d in cases if claim(f, a.a) and claim(f, a.b)]
sample = random.Random(a.seed).sample(shared, min(a.shared_sample, len(shared)))

st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}
todo = []
for group, arms in ((only_a, [a.a]), (only_b, [a.b]), (sample, [a.a, a.b])):
    for f, d in group:
        for arm in arms:
            k = "%s|%s|%d|%d" % (f, arm, claim(f, arm), a.verify_nodes)
            if k not in st:
                todo.append((k, f, claim(f, arm)))
todo = list({k: (k, f, c) for k, f, c in todo}.values())
print("  %s d%d-%s: %d paired positions; %s-only claims %d, %s-only claims %d, shared %d (sampling %d)"
      % (a.corpus, a.min_depth, "max" if a.max_depth >= 999 else a.max_depth, len(cases),
         a.a, len(only_a), a.b, len(only_b), len(shared), len(sample)))
print("  MateProver --direct-depth --no-portfolio at the claimed length, %s nodes; %d proofs to run\n"
      % ("{:,}".format(a.verify_nodes), len(todo)), flush=True)
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    for i, (k, verdict) in enumerate(ex.map(lambda t: (t[0], prove(t[1], t[2], a.verify_nodes)), todo), 1):
        st[k] = verdict
        if i % 50 == 0 or i == len(todo):
            Path(a.state).write_text(json.dumps(st))
            print("     %d/%d" % (i, len(todo)), flush=True)
Path(a.state).write_text(json.dumps(st))

verdict = lambda f, arm: st["%s|%s|%d|%d" % (f, arm, claim(f, arm), a.verify_nodes)]


def tally(group, arm):
    c = {"verified": 0, "refuted": 0, "unconfirmed": 0, "error": 0}
    for f, _ in group:
        c[verdict(f, arm)] += 1
    return c


print("  claims only one arm made")
print("  %-10s %5s %9s %8s %12s %6s" % ("arm", "claims", "verified", "refuted", "unconfirmed", "error"))
for arm, group in ((a.a, only_a), (a.b, only_b)):
    c = tally(group, arm)
    print("  %-10s %5d %9d %8d %12d %6d" % (arm, len(group), c["verified"], c["refuted"], c["unconfirmed"], c["error"]))
print("\n  claims both made (sample of %d)" % len(sample))
for arm in (a.a, a.b):
    c = tally(sample, arm)
    print("  %-10s %5d %9d %8d %12d %6d" % (arm, len(sample), c["verified"], c["refuted"], c["unconfirmed"], c["error"]))

print("\n  paired, on VERIFIED discordant claims only: %s against %s" % (a.a, a.b))
print("  %-9s %8s %8s %8s" % ("band", "a only", "b only", "p"))
W = L = 0
for lo, hi in BANDS:
    name = "d%d-%s" % (lo, hi if hi < 999 else "+")
    w = sum(1 for f, d in only_a if band_name(d) == name and verdict(f, a.a) == "verified")
    l_ = sum(1 for f, d in only_b if band_name(d) == name and verdict(f, a.b) == "verified")
    if w or l_ or any(band_name(d) == name for _, d in cases):
        print("  %-9s %8d %8d %8.4f" % (name, w, l_, sign_p(w, l_)))
    W, L = W + w, L + l_
print("  %-9s %8d %8d %8.4f" % ("ALL", W, L, sign_p(W, L)))
print("\n  Refuted claims were counted as solved by vs_stockfish.py; unconfirmed ones may be either.")
print("\n=== VERIFY CLAIMS ENDED ===")
