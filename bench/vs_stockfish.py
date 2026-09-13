#!/usr/bin/env python3
"""MateHunter against stock Stockfish 19 -- and where MateEval's effect lives.

Every MateHunter result recorded so far is against Huntsman, a fork a decade
old, or against MateHunter's own settings. Neither says anything a Stockfish
developer would act on. The comparison that does is the fork against the engine
it forks, on positions it was never tuned on, with nothing else varied.

MateHunter is now a Stockfish 19 derivative, so that comparison is exact: the
same source, the same network, the same compiler and flags. With every mate
option off it must bench node-for-node identical to stock, and the `mh19-off`
arm is that control run over the whole corpus rather than bench's handful of
positions. If it is not indistinguishable from `sf19`, nothing else here means
anything.

THE MECHANISM. MateEval replaces the static evaluation with a king-danger
score. The static evaluation has two kinds of consumer in Stockfish's search:

  main search   razoring, futility and null-move conditions, the improving
                flag, shallow-pruning margins, reduction adjustments
  quiescence    stand-pat, quiescence futility, and the leaf values that are
                backed up the tree

`MateEvalMain` and `MateEvalQS` route the king-danger score to one of them and
leave NNUE in the other. Comparing each against the all-off control, and the
full evaluator against each, says which consumer carries the effect -- which
is the question every earlier explanation answered by assertion. An evaluation
cached in the TT by one channel is never served to the other, so the two arms
really are separated; the correction histories are shared, which is a residual
coupling and is stated rather than hidden.

The split is not free, and bench shows it. At depth 13 stock searches 2.50M
nodes, the full evaluator 5.75M, quiescence-only 25.8M and main-search-only
60.0M. Routing different evaluations to the two consumers puts two scales in
one search -- a razoring or futility margin built from one is compared with a
quiescence value from the other -- so the channel arms measure a consumer AND a
scale mismatch, and cannot be read alone. Three arms that keep one consistent
evaluation throughout separate the explanations instead:

  mh19-null      a constant evaluation: is the effect just the absence of NNUE?
  mh19-escapes   escape squares only: which part of the signal carries it?
  mh19-noprune   NNUE with razoring, futility and null-move pruning off: is
                 MateEval simply suppressing eval-based pruning?

ROUND 3 -- WHICH CONSUMER. The constant evaluation matching the full evaluator
means the gain is the absence of NNUE's evaluation, so the question becomes which
of the search's consumers of that evaluation NNUE misleads. `MateEvalOff` switches
them off one bit at a time. Each is run twice: under the constant evaluation
(`null-no-*` against `mh19-null`) and under NNUE (`nnue-no-*` against `mh19-off`).
A consumer that carries the effect should recover part of the gain when switched
off under NNUE. None of these arms is in the default set; name them in --arms.

TIME BUDGETS. `--movetime` replaces the node budget with a clock. The constant
evaluation also searches faster, so a node budget understates it; a clock does
not, but a clock makes the result depend on machine load, so run it on an
otherwise idle machine and keep --jobs below the physical core count.

PAIRED, node-budgeted, single-threaded, scored with the mate-sign check
(0 < dm <= N). Node budgets make the result independent of machine load, so
arms run many-wide without one poisoning another. Discordant pairs and a
two-sided sign test per band are the result; totals are shown for orientation.

The checkpoint key includes the node budget. A key without it once replayed a
previous run's results under a new budget without a word.
"""
import argparse
import json
import random
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

import config  # paths: see bench/config.py

BIN = config.ENGINES
EPD = config.corpus("chestuci.epd")
BM = re.compile(r"\bbm\s+#(\d+)")
MATE = re.compile(r"\bscore\s+mate\s+(-?\d+)")
NODES_RE = re.compile(r"\bnodes\s+(\d+)")
TIME_RE = re.compile(r"\btime\s+(\d+)")

BASE = {"Threads": 1, "Hash": 256}
# Every mate toggle is set EXPLICITLY. MateEval defaults TRUE in the fork, so
# relying on a default is how an "off" arm silently runs as the shipped profile.
MH_OFF = dict(BASE, MateMode="false", MateEval="false", MateEvalMain="false", MateEvalQS="false",
              MateEvalNull="false", MateNoRazor="false", MateNoFutility="false", MateNoNull="false",
              MateEvalOff=0)
ARMS = {
    "sf19":      ("sf19", dict(BASE)),
    "mh19-off":  ("matehunter19", dict(MH_OFF)),
    "mh19":      ("matehunter19", dict(MH_OFF, MateEval="true")),
    "mh19-main": ("matehunter19", dict(MH_OFF, MateEvalMain="true")),
    "mh19-qs":   ("matehunter19", dict(MH_OFF, MateEvalQS="true")),
    "mh19-null": ("matehunter19", dict(MH_OFF, MateEval="true", MateEvalNull="true")),
    "mh19-escapes": ("matehunter19", dict(MH_OFF, MateEval="true", MateCheckW=0, MateExposeW=0,
                                          MateDefendW=0, MateAttackW=0, MateNearW=0)),
    "mh19-noprune": ("matehunter19", dict(MH_OFF, MateNoRazor="true", MateNoFutility="true",
                                          MateNoNull="true")),
}
COMPARISONS = [
    ("mh19", "sf19", "MateHunter (shipped profile) against stock Stockfish 19"),
    ("mh19-off", "sf19", "CONTROL: every mate option off must be indistinguishable from stock"),
    ("mh19-main", "mh19-off", "MECHANISM: king danger in the main search only"),
    ("mh19-qs", "mh19-off", "MECHANISM: king danger in quiescence only"),
    ("mh19", "mh19-main", "MECHANISM: what quiescence adds on top of the main search"),
    ("mh19", "mh19-qs", "MECHANISM: what the main search adds on top of quiescence"),
    ("mh19-null", "mh19-off", "MECHANISM: a constant evaluation -- is it just the absence of NNUE?"),
    ("mh19", "mh19-null", "MECHANISM: what the king-danger signal adds over a constant evaluation"),
    ("mh19-escapes", "mh19", "MECHANISM: escape squares alone against the full evaluator"),
    ("mh19-noprune", "mh19-off", "MECHANISM: NNUE with eval-based pruning switched off"),
    ("mh19", "mh19-noprune", "MECHANISM: MateEval against simply switching that pruning off"),
]
CORE_ARMS = list(ARMS)
EVAL_OFF = {1: "improving", 2: "ordering", 4: "probcut", 8: "capfut", 16: "quietfut",
            32: "movecount", 64: "lmreval", 128: "qsfut", 256: "corrhist", 512: "aspiration",
            1024: "bonusscale", 2048: "correval"}
for bit, tag in EVAL_OFF.items():
    ARMS["null-no-" + tag] = ("matehunter19", dict(ARMS["mh19-null"][1], MateEvalOff=bit))
    ARMS["nnue-no-" + tag] = ("matehunter19", dict(MH_OFF, MateEvalOff=bit))
    COMPARISONS.append(("null-no-" + tag, "mh19-null",
                        "CONSUMER, constant evaluation: %s switched off" % tag))
    COMPARISONS.append(("nnue-no-" + tag, "mh19-off",
                        "CONSUMER, NNUE: %s switched off" % tag))
BANDS = [(10, 13), (14, 17), (18, 21), (22, 25), (26, 30), (31, 999)]


def go(arm, fen, depth, budget):
    binary, opts = ARMS[arm]
    p = subprocess.Popen([str(BIN / binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, bufsize=1, errors="replace")
    lines, done = [], threading.Event()

    def rd():
        try:
            for line in p.stdout:
                lines.append(line)
                if line.startswith("bestmove"):
                    break
        finally:
            done.set()
    threading.Thread(target=rd, daemon=True).start()
    cmds = (["uci", "isready"] + ["setoption name %s value %s" % kv for kv in opts.items()]
            + ["isready", "ucinewgame", "position fen %s 0 1" % fen, "go mate %d %s" % (depth, budget)])
    try:
        p.stdin.write("\n".join(cmds) + "\n")
        p.stdin.flush()
        done.wait(timeout=1800)
    except OSError:
        pass
    finally:
        try:
            p.stdin.write("quit\n")
            p.stdin.flush()
            p.wait(timeout=5)
        except Exception:
            p.kill()
    best, last_nodes, last_ms = None, 0, 0
    for line in lines:
        m = MATE.search(line)
        if m:
            dm = int(m.group(1))
            if 0 < dm <= depth:  # negative = the side to move is BEING mated
                best = dm if best is None else min(best, dm)
        n = NODES_RE.search(line)
        t = TIME_RE.search(line)
        if n:
            last_nodes = int(n.group(1))
        if t:
            last_ms = int(t.group(1))
    return best, last_nodes, last_ms


def sign_p(w, l):
    n = w + l
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0


ap = argparse.ArgumentParser()
ap.add_argument("--min-depth", type=int, default=14)
ap.add_argument("--max-depth", type=int, default=999)
ap.add_argument("--n", type=int, default=0, help="0 = every position in the depth range")
ap.add_argument("--seed", default="chestuci-h2h")
ap.add_argument("--nodes", type=int, default=10_000_000)
ap.add_argument("--movetime", type=int, default=0,
                help="milliseconds per position; replaces --nodes when set")
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--arms", default=",".join(CORE_ARMS))
ap.add_argument("--state", default=config.results("vs_stockfish_state.json"))
a = ap.parse_args()
arms = [x for x in a.arms.split(",") if x]
unknown = [x for x in arms if x not in ARMS]
if unknown:
    sys.exit("unknown arm(s): %s" % unknown)

# Pre-flight. A fork that does not know the channel options would accept the
# setoption, ignore it, and run every mechanism arm as the all-off control.
for binary in sorted({ARMS[x][0] for x in arms}):
    path = BIN / binary
    if not path.exists():
        sys.exit("FAIL: %s not found" % path)
if any(ARMS[x][0] == "matehunter19" for x in arms):
    probe = subprocess.run([str(BIN / "matehunter19")], input="uci\nquit\n",
                           capture_output=True, text=True, errors="replace", timeout=30).stdout
    for needed in ("MateEval ", "MateEvalMain", "MateEvalQS", "MateEvalOff"):
        if needed not in probe:
            sys.exit("FAIL: matehunter19 does not advertise %s" % needed.strip())

Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

pool = []
for line in EPD.read_text(encoding="utf-8", errors="replace").splitlines():
    m = BM.search(line)
    if not m or line.startswith("%"):
        continue
    d = int(m.group(1))
    if a.min_depth <= d <= a.max_depth:
        pool.append((" ".join(line.split(" bm ")[0].split()[:4]), d))
random.Random(a.seed).shuffle(pool)
cases = pool[:a.n] if a.n else pool
budget = ("movetime %d" % a.movetime) if a.movetime else ("nodes %d" % a.nodes)
budget_key = ("t%d" % a.movetime) if a.movetime else str(a.nodes)
key = lambda f, arm: "%s|%s|%s" % (f, arm, budget_key)
print("  ChestUCI d%d-%s: %d positions; %s, 1 thread, arms %s"
      % (a.min_depth, "max" if a.max_depth >= 999 else a.max_depth, len(cases),
         ("%d ms a position" % a.movetime) if a.movetime else ("{:,} nodes".format(a.nodes)),
         ",".join(arms)), flush=True)

jobs = [(f, d, arm) for f, d in cases for arm in arms if key(f, arm) not in st]
print("  %d arm-positions to run\n" % len(jobs), flush=True)


def work(j):
    f, d, arm = j
    dm, nodes, ms = go(arm, f, d, budget)
    return key(f, arm), {"dm": dm, "nodes": nodes, "ms": ms}


lock = threading.Lock()
done = 0
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    for k, v in ex.map(work, jobs):
        with lock:
            st[k] = v
            done += 1
            if done % 50 == 0 or done == len(jobs):
                Path(a.state).write_text(json.dumps(st))
                print("     %d/%d" % (done, len(jobs)), flush=True)

print()
for arm in arms:
    rs = [st[key(f, arm)] for f, _ in cases if key(f, arm) in st]
    tn = sum(r["nodes"] for r in rs)
    tm = sum(r["ms"] for r in rs)
    print("  %-10s solved %4d/%d   nps ~ %s" % (arm, sum(1 for r in rs if r["dm"]), len(rs),
          "{:,}".format(int(1000 * tn / tm)) if tm else "-"))

for x, y, title in COMPARISONS:
    if x not in arms or y not in arms:
        continue
    solved = lambda arm: {f for f, _ in cases if st.get(key(f, arm), {}).get("dm")}
    sx, sy = solved(x), solved(y)
    print("\n  %s\n  %s vs %s" % (title, x, y))
    print("  %-9s %5s %8s %8s %8s %8s %8s" % ("band", "n", x[:8], y[:8], "x only", "y only", "p"))
    W = L = 0
    for lo, hi in BANDS:
        g = {f for f, d in cases if lo <= d <= hi}
        if not g:
            continue
        w, l = len((sx - sy) & g), len((sy - sx) & g)
        W += w
        L += l
        print("  d%-2d-%-4s %5d %8d %8d %8d %8d %8.4f"
              % (lo, hi if hi < 999 else "+", len(g), len(sx & g), len(sy & g), w, l, sign_p(w, l)))
    print("  %-9s %5d %8d %8d %8d %8d %8.4f" % ("ALL", len(cases), len(sx), len(sy), W, L, sign_p(W, L)))

print("\n  Read the BAND rows. A pooled null can be two opposite effects cancelling.")
print("\n=== VS STOCKFISH ENDED ===", flush=True)
