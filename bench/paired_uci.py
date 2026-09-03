#!/usr/bin/env python3
"""MateHunter vs Huntsman with enough positions to actually see a difference.

Every prior comparison ran at n=30 per band. The paired instrument data says
what that buys: |d|/se of 0.29, 0.12, 0.73 and 1.00 across the four bands.
NOTHING reaches the project's own visibility threshold of 2. The raw-count
gaps quoted for a week ("131 vs 140", "45 vs 51") are noise-level, and the
only defensible statement has been "indistinguishable at this n".

So before anyone tries to make MateHunter beat Huntsman, build an instrument
that could see it happen. ChestUCI.epd ships 6,728 problems, 953 at d>=14, with
no shared provenance with matetrack - the corpus MateHunter was tuned on. That
is both more power and an independent test in one run.

PAIRED, node-budgeted, single-threaded. Both engines are Stockfish 18 forks, so
unlike a DFPN-vs-alpha-beta comparison a node is close to the same unit; the
nps of each is measured and reported so the reader can judge the residual.
Node budgets let the arms run twelve-wide without wall-clock contention
poisoning one arm more than the other.

Every mate toggle is set EXPLICITLY. MateHunter's MateMode/MateEval default
FALSE; Huntsman's MateSearch defaults TRUE. Relying on either default is how
an arm silently runs as an ordinary engine and a null completes cleanly.

Scored with the mate-sign check: a NEGATIVE UCI mate score means the side to
move is being mated. Require 0 < dm <= N.

Reports per-band counts, discordant pairs, and a two-sided sign test. The
count totals are shown but the discordant pairs are the result.
"""
import argparse, json, random, re, subprocess, sys, threading, time
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

ARMS = {
    "matehunter": (str(BIN / "hunt18-clean"),
                   {"Threads": 1, "Hash": 256, "MateMode": "true", "MateEval": "true"}),
    "huntsman":   (str(BIN / "huntsman"),
                   {"Threads": 1, "Hash": 256, "MateSearch": "true"}),
    # MECHANISM ARM. MateHunter loses to Huntsman at d26+ (+8/-30, p=0.0005)
    # and beats it at d18-21 (+16/-2, p=0.001). MateEval is a king-danger
    # heuristic tuned shallow - the obvious suspect for a deep deficit. This
    # arm is MateHunter with ONLY MateMode, no MateEval. If it closes the deep
    # gap the evaluator is what misleads deep; if it also loses the d18-21
    # lead, the same evaluator is what wins shallow, and the fix is depth-
    # conditional rather than "turn it off".
    "matehunter-noeval": (str(BIN / "hunt18-clean"),
                   {"Threads": 1, "Hash": 256, "MateMode": "true", "MateEval": "false"}),
    # MECHANISM ARM 2. MateEval is exonerated (off, MateHunter loses everywhere).
    # Remaining suspect for the d26+ loss: MateMode itself, which disables
    # razoring, futility and null-move and adds a ply of check relief. Those
    # are sound for PROVING but cost node efficiency, and at depth that may be
    # what Huntsman keeps. This arm keeps the evaluator and restores pruning.
    "matehunter-eval-nomode": (str(BIN / "hunt18-clean"),
                   {"Threads": 1, "Hash": 256, "MateMode": "false", "MateEval": "true"}),
}


def go(arm, fen, depth, nodes):
    path, opts = ARMS[arm]
    p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, bufsize=1,
                         errors="replace")
    lines, done = [], threading.Event()

    def rd():
        try:
            for l in p.stdout:
                lines.append(l)
                if l.startswith("bestmove"):
                    break
        finally:
            done.set()
    threading.Thread(target=rd, daemon=True).start()
    cmds = ["uci", "isready"] + ["setoption name %s value %s" % kv for kv in opts.items()] + \
           ["isready", "ucinewgame", "position fen %s 0 1" % fen,
            "go mate %d nodes %d" % (depth, nodes)]
    try:
        p.stdin.write("\n".join(cmds) + "\n"); p.stdin.flush()
        done.wait(timeout=1800)
    except OSError:
        pass
    finally:
        try:
            p.stdin.write("quit\n"); p.stdin.flush(); p.wait(timeout=5)
        except Exception:
            p.kill()
    best, last_nodes, last_ms = None, 0, 0
    for l in lines:
        m = MATE.search(l)
        if m:
            dm = int(m.group(1))
            if 0 < dm <= depth:          # negative = BEING mated; not a solve
                best = dm if best is None else min(best, dm)
        n = NODES_RE.search(l); t = TIME_RE.search(l)
        if n: last_nodes = int(n.group(1))
        if t: last_ms = int(t.group(1))
    return best, last_nodes, last_ms


ap = argparse.ArgumentParser()
ap.add_argument("--min-depth", type=int, default=14)
ap.add_argument("--n", type=int, default=400)
ap.add_argument("--nodes", type=int, default=10_000_000)
ap.add_argument("--jobs", type=int, default=8)
ap.add_argument("--state", default=config.results("h2h_chestuci_state.json"))
a = ap.parse_args()
Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

pool = []
for line in EPD.read_text(encoding="utf-8", errors="replace").splitlines():
    m = BM.search(line)
    if not m or line.startswith("%"):
        continue
    d = int(m.group(1))
    if d < a.min_depth:
        continue
    fen = " ".join(line.split(" bm ")[0].split()[:4])
    pool.append((fen, d))
random.Random("chestuci-h2h").shuffle(pool)
cases = pool[:a.n]
print("  ChestUCI d>=%d: %d available, %d sampled; %s nodes, 1 thread each"
      % (a.min_depth, len(pool), len(cases), "{:,}".format(a.nodes)), flush=True)

jobs = [(f, d, arm) for f, d in cases for arm in ARMS if "%s|%s" % (f, arm) not in st]
print("  %d arm-positions to run\n" % len(jobs), flush=True)


def work(j):
    f, d, arm = j
    dm, nodes, ms = go(arm, f, d, a.nodes)
    return "%s|%s" % (f, arm), {"depth": d, "dm": dm, "nodes": nodes, "ms": ms}


done = 0
with ThreadPoolExecutor(max_workers=a.jobs) as pool_:
    for k, v in pool_.map(work, jobs):
        st[k] = v; done += 1
        if done % 40 == 0 or done == len(jobs):
            Path(a.state).write_text(json.dumps(st))
            print("     %d/%d" % (done, len(jobs)), flush=True)
Path(a.state).write_text(json.dumps(st))

# nps calibration: are the arms spending a node at the same rate?
for arm in ARMS:
    rs = [st["%s|%s" % (f, arm)] for f, _ in cases if "%s|%s" % (f, arm) in st]
    tn = sum(r["nodes"] for r in rs); tm = sum(r["ms"] for r in rs)
    print("  %-11s nps ~ %s" % (arm, "{:,}".format(int(1000 * tn / tm)) if tm else "-"))

bands = [(14, 17), (18, 21), (22, 25), (26, 30), (31, 99)]
hs_all = {f for f, _ in cases if st.get("%s|huntsman" % f, {}).get("dm")}
for mh_arm in [x for x in ARMS if x != "huntsman"]:
    if not any("%s|%s" % (f, mh_arm) in st for f, _ in cases):
        continue
    print()
    print("  %s vs huntsman" % mh_arm)
    print("  %-8s %5s %11s %10s %9s %9s %8s" % ("band", "n", "MH-arm", "huntsman", "MH only", "HS only", "p"))
    W = L = 0
    for lo, hi in bands:
        g = [(f, d) for f, d in cases if lo <= d <= hi]
        if not g:
            continue
        mh = {f for f, _ in g if st.get("%s|%s" % (f, mh_arm), {}).get("dm")}
        hs = {f for f, _ in g if f in hs_all}
        w, l = len(mh - hs), len(hs - mh); n = w + l; W += w; L += l
        p = min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2**n) if n else 1.0
        print("  d%-2d-%-3d %5d %11d %10d %9d %9d %8.3f" % (lo, hi, len(g), len(mh), len(hs), w, l, p))
    n = W + L
    p = min(1.0, 2 * sum(comb(n, i) for i in range(min(W, L) + 1)) / 2**n) if n else 1.0
    mh_all = sum(1 for f, _ in cases if st.get("%s|%s" % (f, mh_arm), {}).get("dm"))
    print("  %-8s %5d %11d %10d %9d %9d %8.4f" % ("ALL", len(cases), mh_all, len(hs_all), W, L, p))
    print("  discordant %d: %s +%d / -%d -> %s" % (n, mh_arm, W, L,
          "not established" if p > 0.05 else ("%s AHEAD, p=%.4f" % (mh_arm if W > L else "huntsman", p))))
print()
print("  Read the BAND rows. A pooled null can be two opposite effects cancelling.")
print()
print("=== H2H CHESTUCI ENDED ===", flush=True)
