#!/usr/bin/env python3
"""The finder lane measured against the RIGHT baseline.

The published figure (7/60 -> 31/60, "+24") used
`--iterative-depth --no-portfolio` as its baseline while scoring the lane arm
with `--direct-depth`. The control run shows what that was worth:

    --iterative-depth --no-portfolio  20M nodes ->  7/60
    --direct-depth    --no-portfolio  20M nodes -> 36/60

So the mode change alone is +29, and mateprover asking the question DIRECTLY
(36) already beats the published lane composite (31) - while spending 20M nodes
against the lane's 44M. The entire headline was the mode change, and the lane
as measured was dominated by the trivial alternative nobody ran.

What is still genuinely open is the correctly specified question: on the
positions `--direct-depth` CANNOT do at full budget, does a proposer add
anything? Baseline 36/60, so 24 positions are in play. This measures exactly
that and nothing else - identical budget, identical mode, the ONLY difference
being whether a finder is consulted.
"""
import argparse, json, re, subprocess, sys, threading
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pools import by_depth
import config  # paths: see bench/config.py

BIN = config.ENGINES
MP = str(BIN / "mateprover")
DM = re.compile(r"\bdm (\d+)")
MATE = re.compile(r"\bscore\s+mate\s+(-?\d+)")
# matefish had the best precision of the three proposers measured, and needs
# BOTH of these: ProofNumberSearch defaults false, and PNS Hash is a separate
# table from Hash defaulting to 32 MB, at which it abandons hard searches.
MF_OPTS = {"Threads": 1, "Hash": 256, "PNS Hash": 4096, "ProofNumberSearch": "true"}


def prove(fen, depth, nodes):
    try:
        p = subprocess.run(
            [MP, "-z", str(depth), "--direct-depth", "--no-portfolio",
             "--threads", "1", "--node-limit", str(nodes), "-"],
            input="%s bm #%d;\n" % (fen, depth), capture_output=True,
            text=True, errors="replace", timeout=3600)
    except subprocess.TimeoutExpired:
        return False
    return bool(DM.search(p.stdout or ""))


def find(fen, depth, nodes):
    p = subprocess.Popen([str(BIN / "matefish")], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, bufsize=1, errors="replace")
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
    cmds = ["uci", "isready"] + ["setoption name %s value %s" % kv for kv in MF_OPTS.items()] + \
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
    best = None
    for l in lines:
        m = MATE.search(l)
        if m:
            dm = int(m.group(1))
            if 0 < dm <= depth:      # negative = the side to move is BEING mated
                best = dm if best is None else min(best, dm)
    return best


ap = argparse.ArgumentParser()
ap.add_argument("--depths", default="12,14,16,18")  # LINT-OK: ONE-BAND - four bands
ap.add_argument("--per-depth", type=int, default=15)
ap.add_argument("--nodes", type=int, default=20_000_000)
ap.add_argument("--verify-nodes", type=int, default=20_000_000)
ap.add_argument("--state", default=config.results("genverify_corrected_state.json"))
a = ap.parse_args()
Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

cases = []
for d in [int(x) for x in a.depths.split(",")]:
    for c in by_depth(d, d, per_depth=a.per_depth, seed="genver"):
        cases.append((c["fen4"], d))
print("  %d positions, --direct-depth baseline at %s nodes, matefish proposer\n"
      % (len(cases), "{:,}".format(a.nodes)), flush=True)

for i, (fen, d) in enumerate(cases, 1):
    if fen in st:
        continue
    base = prove(fen, d, a.nodes)
    claim = verified = None
    if not base:
        claim = find(fen, d, a.nodes)
        verified = bool(claim) and prove(fen, claim, a.verify_nodes)
    st[fen] = {"depth": d, "base": base, "claim": claim, "verified": bool(verified)}
    Path(a.state).write_text(json.dumps(st))
    if i % 10 == 0 or i == len(cases):
        print("     %d/%d" % (i, len(cases)), flush=True)

base = sum(1 for f, _ in cases if st[f]["base"])
add = sum(1 for f, _ in cases if not st[f]["base"] and st[f]["verified"])
claimed = sum(1 for f, _ in cases if not st[f]["base"] and st[f]["claim"])
print("\n  mateprover --direct-depth alone     %d/%d" % (base, len(cases)))
print("  proposer claimed on                 %d of the %d it missed" % (claimed, len(cases) - base))
print("  of those, VERIFIED                  %d" % add)
print("  lane total                          %d/%d  (%+d)" % (base + add, len(cases), add))
print()
if add == 0:
    print("  -> THE PROPOSER ADDS NOTHING once the baseline asks the same")
    print("     question. The published +24 was entirely the mode change.")
else:
    print("  -> the proposer is worth %+d over a correctly configured baseline," % add)
    print("     against the %+d originally published." % 24)
print("\n=== GENVERIFY CORRECTED ENDED ===", flush=True)
