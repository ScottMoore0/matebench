#!/usr/bin/env python3
"""Is there ANY headroom for a ninth portfolio lane? Gate for the learned-lane idea.

The proposal is a lane whose restriction comes from a learned mating-strength
score rather than from a structural rule. Before writing the C++ for it, there
is a much cheaper question that bounds the whole idea:

    Of the positions the shipped 8-lane portfolio FAILS, can any restriction
    setting solve them at all?

If the answer is zero, the portfolio already captures what attacker-restriction
can do on this corpus, and a learned lane cannot help either - it would be a
different way of choosing from a family that has nothing left to give. If the
answer is more than zero, there is headroom, and how a lane is chosen becomes
worth improving.

THE SHIPPED LANES, greedy set cover over matetrack MATE-IN-8:

    unrestricted  K2  K3  X2  R2  C4  R1  Rq2

Note the corpus they were derived on. Nothing was re-derived for depth, which is
why unshipped settings are worth trying at all.

CANDIDATES are unshipped values in the same four dimensions:
    K1 K4   (K2, K3 shipped)      X1 X3   (X2 shipped)
    C2 C6   (C4 shipped)          R3 R4   (R1, R2 shipped)
Rq variants cannot be tested through the CLI: threat_depth is parsed unsigned,
so the shipped Rq2 (-2) has no reachable neighbours.

BUDGET IS DELIBERATELY UNFAIR TO THE PORTFOLIO. Each candidate gets the FULL
node budget alone, while the portfolio splits the same budget across eight
lanes. So a candidate that cannot solve a position here could certainly not
solve it as a lane holding a fraction of the budget. That makes the result an
UPPER BOUND on ninth-lane headroom, which is the only direction that matters:
if the bound is zero, the idea is dead regardless of how the lane is chosen.

Restrictions remove only ATTACKER options, so every solve counted here is a real
mate - no verification step is needed and none of this can produce a false
positive.
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pools import by_depth
import config  # paths: see bench/config.py

MP = str(config.ENGINES / "mateprover")
DM = re.compile(r"\bdm (\d+)")

CANDIDATES = [
    ("K1", ["--restrict-king", "1"]),
    ("K4", ["--restrict-king", "4"]),
    ("X1", ["--restrict-maxdef", "1"]),
    ("X3", ["--restrict-maxdef", "3"]),
    ("C2", ["--restrict-checks", "2"]),
    ("C6", ["--restrict-checks", "6"]),
    ("R3", ["--restrict-threat", "3"]),
    ("R4", ["--restrict-threat", "4"]),
]


def run(fen, depth, extra, nodes):
    argv = [MP, "-z", str(depth), "--direct-depth", "--threads", "1",
            "--node-limit", str(nodes), *extra, "-"]
    try:
        p = subprocess.run(argv, input="%s bm #%d;\n" % (fen, depth),
                           capture_output=True, text=True, errors="replace",
                           timeout=3600)
    except subprocess.TimeoutExpired:
        return False
    return bool(DM.search(p.stdout or ""))


ap = argparse.ArgumentParser()
ap.add_argument("--depths", default="10,12,14")  # LINT-OK: ONE-BAND - three bands
ap.add_argument("--per-depth", type=int, default=15)
ap.add_argument("--nodes", type=int, default=20_000_000)
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--state", default=config.results("lane9_state.json"))
a = ap.parse_args()

Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

cases = []
for d in [int(x) for x in a.depths.split(",")]:
    for c in by_depth(d, d, per_depth=a.per_depth, seed="lane9"):
        cases.append((c["fen4"], d))

ARMS = [("portfolio", [])] + CANDIDATES
print("  %d positions, %s nodes each, %d arms (portfolio + %d candidates)"
      % (len(cases), "{:,}".format(a.nodes), len(ARMS), len(CANDIDATES)), flush=True)
print("  candidates run WITHOUT --no-portfolio disabled? no - each is a single"
      "\n  restricted search, given the full budget the portfolio splits eight ways\n",
      flush=True)

jobs = [(f, d, name, extra) for f, d in cases for name, extra in ARMS
        if "%s|%s" % (f, name) not in st]
print("  %d arm-positions to run\n" % len(jobs), flush=True)


def work(j):
    f, d, name, extra = j
    args = extra if name == "portfolio" else ["--no-portfolio"] + extra
    return "%s|%s" % (f, name), run(f, d, args, a.nodes)


done = 0
with ThreadPoolExecutor(max_workers=a.jobs) as pool:
    for k, v in pool.map(work, jobs):
        st[k] = v
        done += 1
        if done % 25 == 0 or done == len(jobs):
            Path(a.state).write_text(json.dumps(st))
            print("     %d/%d" % (done, len(jobs)), flush=True)
Path(a.state).write_text(json.dumps(st))

solved = {name: {f for f, _ in cases if st.get("%s|%s" % (f, name))}
          for name, _ in ARMS}
port = solved["portfolio"]
missed = {f for f, _ in cases} - port

print("\n  %-14s %8s %14s" % ("arm", "solved", "of portfolio's"))
print("  %-14s %8s %14s" % ("", "", "misses, rescued"))
print("  %-14s %8d %14s" % ("portfolio (8)", len(port), "-"))
rescued_any = set()
for name, _ in CANDIDATES:
    r = solved[name] & missed
    rescued_any |= r
    print("  %-14s %8d %14d" % (name, len(solved[name]), len(r)))

print("\n  portfolio solved %d/%d, missed %d" % (len(port), len(cases), len(missed)))
print("  positions rescued by AT LEAST ONE unshipped restriction: %d"
      % len(rescued_any))
print()
if not rescued_any:
    print("  -> NO HEADROOM. Every position the portfolio misses is missed by")
    print("     every candidate restriction too, each given the FULL budget the")
    print("     portfolio splits eight ways. Attacker-restriction as a family is")
    print("     exhausted on this corpus, so a ninth lane cannot help however it")
    print("     is chosen - learned or structural. The learned-lane idea is dead")
    print("     at this operating point, and no C++ needs writing to find out.")
else:
    print("  -> HEADROOM EXISTS: %d position(s) reachable by a restriction the"
          % len(rescued_any))
    print("     portfolio does not carry. How a lane is CHOSEN is therefore worth")
    print("     improving, and a learned restriction is worth building. Note this")
    print("     is an UPPER BOUND - a real lane holds a fraction of the budget.")
print("\n=== LANE9 HEADROOM ENDED ===", flush=True)
