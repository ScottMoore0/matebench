#!/usr/bin/env python3
"""The control generate_verify.py never ran, and its absence inflates the +24.

generate_verify.py reported 7/60 -> 31/60 for the finder lane. Its BASELINE was

    mateprover --iterative-depth --no-portfolio --node-limit 20M   -> 7/60

and its lane arm verified claims with --direct-depth. That changes TWO things
at once: it adds a proposer, and it stops asking for the SHORTEST mate. The
headline therefore attributes to the finder whatever share belongs to dropping
minimality.

Today's head-to-head puts a number on how large that share could be: on 60
other positions --direct-depth scored 45 where --iterative-depth scored 41.

This runs the missing arm - same positions, same seed, same budget, same
--no-portfolio, ONLY the mode changed:

    A  --iterative-depth   the published baseline, expect ~7/60
    B  --direct-depth      the same question the lane's verification asks

B is the honest baseline for the lane, because the lane's output is "a mate
within N" and B is mateprover answering exactly that unaided. Whatever B
scores above A is NOT the finder's contribution and must come off the +24.
"""
import argparse, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pools import by_depth
import config  # paths: see bench/config.py

MP = str(config.ENGINES / "mateprover")
DM = re.compile(r"\bdm (\d+)")


def solve(fen, depth, mode, nodes):
    try:
        p = subprocess.run(
            [MP, "-z", str(depth), mode, "--no-portfolio", "--threads", "1",
             "--node-limit", str(nodes), "-"],
            input="%s bm #%d;\n" % (fen, depth), capture_output=True,
            text=True, errors="replace", timeout=3600)
    except subprocess.TimeoutExpired:
        return False
    return bool(DM.search(p.stdout or ""))


ap = argparse.ArgumentParser()
ap.add_argument("--depths", default="12,14,16,18")  # LINT-OK: ONE-BAND - four bands
ap.add_argument("--per-depth", type=int, default=15)
ap.add_argument("--nodes", type=int, default=20_000_000)
ap.add_argument("--jobs", type=int, default=6)
ap.add_argument("--state", default=config.results("genverify_control_state.json"))
a = ap.parse_args()
Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

cases = []
for d in [int(x) for x in a.depths.split(",")]:
    # SAME seed as generate_verify.py, so these are the SAME 60 positions.
    for c in by_depth(d, d, per_depth=a.per_depth, seed="genver"):
        cases.append((c["fen4"], d))
print("  %d positions (seed 'genver' - the same set), %s nodes, --no-portfolio"
      % (len(cases), "{:,}".format(a.nodes)), flush=True)

jobs = [(f, d, m) for f, d in cases for m in ("--iterative-depth", "--direct-depth")
        if "%s|%s" % (f, m) not in st]
print("  %d arm-positions to run\n" % len(jobs), flush=True)


def work(j):
    f, d, m = j
    return "%s|%s" % (f, m), solve(f, d, m, a.nodes)


done = 0
with ThreadPoolExecutor(max_workers=a.jobs) as pool:
    for k, v in pool.map(work, jobs):
        st[k] = v
        done += 1
        if done % 12 == 0 or done == len(jobs):
            Path(a.state).write_text(json.dumps(st))
            print("     %d/%d" % (done, len(jobs)), flush=True)
Path(a.state).write_text(json.dumps(st))

it = sum(1 for f, _ in cases if st.get("%s|--iterative-depth" % f))
di = sum(1 for f, _ in cases if st.get("%s|--direct-depth" % f))
print("\n  %-34s %d/%d" % ("--iterative-depth (published base)", it, len(cases)))
print("  %-34s %d/%d" % ("--direct-depth (honest base)", di, len(cases)))
print("\n  dropping minimality alone is worth %+d positions." % (di - it))
print("  The published lane figure was 7 -> 31, i.e. +24 attributed to the")
print("  finder. Of that, %d belongs to the MODE CHANGE, leaving about %+d"
      % (di - it, 31 - di))
print("  for the proposer - IF 31 is reproduced on this same set.")
print("\n=== GENVERIFY CONTROL ENDED ===", flush=True)
