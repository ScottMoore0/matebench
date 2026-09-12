#!/usr/bin/env python3
"""MateProver against Matefish. The comparison that was never run.

MateProver has been benchmarked extensively against Chest 3.19 - a program
whose copyright is 1994 and whose 3.16 release is dated June 1999 - and against
nothing else. Matefish is a modern proof-number-search mate solver,
architecturally the closest thing to MateProver that exists, and it has never
been measured against it. Publishing "better than Chest" without this number is
leaving the obvious question to a reader with a terminal.

CLAIMS MUST BE MATCHED, and here they are not the same by default. Probed over
nine cases: `go mate N` on a position whose shortest mate is 2, 3 or 4 returns
`score mate N` for N = true, true+5 and true+12 EVERY time. Matefish echoes the
bound. It answers "is there a mate within N", never "the shortest mate is N".
So:

    FINDING     matefish `go mate N`  vs  mateprover --direct-depth -z N
                Same question, comparable, and the headline table.
    MINIMALITY  mateprover --iterative-depth -z N, with NO counterpart.
                Matefish cannot do this at all. That is categorical, not a
                margin, and is reported separately rather than folded in.

TIME, not nodes. This project prefers deterministic node budgets, and that rule
is right for comparing configurations of ONE engine. Across engines a node is
not the same unit - a DFPN node and an alpha-beta node count different work -
so a node budget would silently hand the advantage to whichever engine defines
a node more cheaply. Wall clock is the only budget both engines spend the same
way. Run this on an IDLE machine and check the load first.

MATEFISH'S CLAIMS ARE VERIFIED, not taken. The finder lane measured this fork
family over-claiming, and scoring an unverified claim as a solve would inflate
matefish exactly where it looks strongest. Each claim is re-proved by
mateprover --direct-depth. Three counts are reported - claimed, verified, and
unverified-within-budget - because a claim that fails to verify in the budget
is not the same as a false one, and reporting it as false would be the mirror
of the error being avoided.

ProofNumberSearch=true is set explicitly. It defaults FALSE, and without it
matefish is not a mate solver at all - it silently runs as ordinary alpha-beta
and claims almost nothing, which reads as weakness rather than as a switch
left off.
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pools import by_depth
import config  # paths: see bench/config.py

BIN = config.ENGINES
MP = str(BIN / "mateprover")
MF = str(BIN / "matefish")
DM = re.compile(r"\bdm (\d+)")
# Negative mate scores mean the side to move is BEING mated. Never abs() this.
MATE = re.compile(r"\bscore\s+mate\s+(-?\d+)")
# "PNS Hash" is a SEPARATE table from "Hash" and is the one proof-number
# search actually uses. At its 32 MB default matefish ABANDONS a d14 search in
# 0.20s; at 1024 it searches for 8.7s and at 8192 it uses a full 20s budget.
# Benchmarking it at the default would have measured a crippled engine and
# produced a flattering, wrong result. It is given 4 GB here - far more than
# mateprover's 256 MB per-table default - so that no reader can attribute the
# outcome to under-resourcing the competitor.
MF_OPTS = {"Threads": 1, "Hash": 256, "PNS Hash": 4096,
           "ProofNumberSearch": "true"}


def mateprover(fen, depth, mode, seconds):
    """(solved?, seconds). Certificate-backed by construction."""
    t0 = time.time()
    try:
        p = subprocess.run(
            [MP, "-z", str(depth), mode, "--threads", "1",
             # LINT-OK: WALL-CLOCK - a node budget is the right rule WITHIN
             # one engine, but a DFPN node and an alpha-beta node are not the
             # same unit, so across engines it would hand the advantage to
             # whichever defines a node more cheaply. Time is the only budget
             # both spend identically. Run on an idle machine.
             "--time-limit", str(seconds), "-"],
            input="%s bm #%d;\n" % (fen, depth), capture_output=True,
            text=True, errors="replace", timeout=seconds * 6 + 120)
    except subprocess.TimeoutExpired:
        return False, time.time() - t0
    out = p.stdout or ""
    solved = bool(DM.search(out))
    # MINIMALITY will not accept a restricted lane's answer.
    #
    # A --time-limit is set on every call here, and that is exactly the
    # condition under which mateprover engages its restriction portfolio. A
    # restricted lane searches the REQUESTED depth directly and never walks the
    # shallower ones, so it can prove "a mate within N" and cannot prove "the
    # shortest mate is N". It says so: OUTPUT_FORMAT.md specifies the opcode
    # `via <name>` on exactly those lines, and documents them as real mates that
    # may not be the shortest.
    #
    # So a `via` line answers the FINDING question and not the MINIMALITY one.
    # Counting it would inflate the single column matefish has no counterpart
    # for -- the categorical claim in this file's header -- which is the one
    # place an overstatement would be least defensible.
    if solved and mode == "--iterative-depth" and "; via " in out:
        solved = False
    return solved, time.time() - t0


def matefish(fen, depth, seconds):
    """(claimed distance or None, seconds). NOT trusted - verified later."""
    t0 = time.time()
    p = subprocess.Popen([MF], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
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
    cmds = ["uci", "isready"] + \
           ["setoption name %s value %s" % kv for kv in MF_OPTS.items()] + \
           ["isready", "ucinewgame", "position fen %s 0 1" % fen,
            "go mate %d movetime %d" % (depth, int(seconds * 1000))]
    try:
        p.stdin.write("\n".join(cmds) + "\n")
        p.stdin.flush()
        done.wait(timeout=seconds * 6 + 120)
    except OSError:
        pass
    finally:
        try:
            p.stdin.write("quit\n")
            p.stdin.flush()
            p.wait(timeout=5)
        except Exception:
            p.kill()
    best = None
    for l in lines:
        m = MATE.search(l)
        if m:
            dm = int(m.group(1))
            # A NEGATIVE mate score means the side to move is BEING mated.
            # Require 0 < dm <= what was asked for.
            if 0 < dm <= depth:
                best = dm if best is None else min(best, dm)
    return best, time.time() - t0


ap = argparse.ArgumentParser()
ap.add_argument("--depths", default="8,10,12,14,16")  # LINT-OK: ONE-BAND - five bands
ap.add_argument("--per-depth", type=int, default=12)
ap.add_argument("--seconds", type=float, default=10.0)
ap.add_argument("--verify-seconds", type=float, default=10.0)
ap.add_argument("--state", default=config.results("vs_matefish_state.json"))
a = ap.parse_args()

Path(a.state).parent.mkdir(parents=True, exist_ok=True)
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}

# Pre-flight: matefish without PNS is not a mate solver, and a run that forgets
# it completes cleanly and reads as "matefish is weak".
probe = subprocess.run([MF], input="uci\nquit\n", capture_output=True,
                       text=True, errors="replace", timeout=30)
if "ProofNumberSearch" not in (probe.stdout or ""):
    sys.exit("FAIL: this matefish build has no ProofNumberSearch option.")
if "PNS Hash" not in (probe.stdout or ""):
    sys.exit("FAIL: no `PNS Hash` option - cannot resource matefish fairly.")

cases = []
for d in [int(x) for x in a.depths.split(",")]:
    for c in by_depth(d, d, per_depth=a.per_depth, seed="vsmatefish"):
        cases.append((c["fen4"], d))
print("  %d positions, %.0fs per engine per position, single-threaded"
      % (len(cases), a.seconds), flush=True)
print("  matefish: ProofNumberSearch=true, Hash=256\n", flush=True)

for i, (fen, d) in enumerate(cases, 1):
    key = "%s|%d" % (fen, d)
    if key in st:
        continue
    direct, t_dir = mateprover(fen, d, "--direct-depth", a.seconds)
    shortest, t_sh = mateprover(fen, d, "--iterative-depth", a.seconds)
    claim, t_mf = matefish(fen, d, a.seconds)
    verified = False
    if claim:
        verified, _ = mateprover(fen, claim, "--direct-depth", a.verify_seconds)
    st[key] = {"depth": d, "direct": direct, "shortest": shortest,
               "claim": claim, "verified": verified,
               "t_direct": t_dir, "t_mf": t_mf}
    Path(a.state).write_text(json.dumps(st))
    if i % 5 == 0 or i == len(cases):
        print("     %d/%d" % (i, len(cases)), flush=True)

rows = [st["%s|%d" % (f, d)] for f, d in cases if "%s|%d" % (f, d) in st]
depths = sorted({r["depth"] for r in rows})

print("\n  FINDING - a mate within N. Matched claims, the comparable table.")
print("  %-6s %5s %14s %12s %12s" % ("band", "n", "mateprover", "matefish", "matefish"))
print("  %-6s %5s %14s %12s %12s" % ("", "", "--direct-depth", "claimed", "VERIFIED"))
tot = [0, 0, 0, 0]
for d in depths:
    g = [r for r in rows if r["depth"] == d]
    mp = sum(1 for r in g if r["direct"])
    cl = sum(1 for r in g if r["claim"])
    vf = sum(1 for r in g if r["verified"])
    tot = [tot[0] + len(g), tot[1] + mp, tot[2] + cl, tot[3] + vf]
    print("  d%-5d %5d %14d %12d %12d" % (d, len(g), mp, cl, vf))
print("  %-6s %5d %14d %12d %12d" % ("TOTAL", *tot))

win = sum(1 for r in rows if r["verified"] and not r["direct"])
lose = sum(1 for r in rows if r["direct"] and not r["verified"])
n = win + lose
print("\n  paired, verified matefish against mateprover --direct-depth:")
print("     matefish +%d / -%d   (%d discordant)" % (win, lose, n))
if n:
    from math import comb
    k = min(win, lose)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)
    print("     sign test p = %.4f -> %s"
          % (p, "significant" if p <= 0.05 else "NOT established"))
else:
    print("     no discordant pairs - nothing is established either way")

unver = sum(1 for r in rows if r["claim"] and not r["verified"])
print("\n  %d of %d matefish claims did not verify within %.0fs. That is NOT the"
      % (unver, tot[2], a.verify_seconds))
print("  same as false: unverified within a budget only means unconfirmed.")

print("\n  MINIMALITY - the shortest mate. Matefish has no counterpart: it")
print("  echoes the bound it is given and cannot answer this at all.")
print("  %-6s %5s %14s %12s" % ("band", "n", "mateprover", "matefish"))
for d in depths:
    g = [r for r in rows if r["depth"] == d]
    print("  d%-5d %5d %14d %12s"
          % (d, len(g), sum(1 for r in g if r["shortest"]), "n/a"))
print("  %-6s %5d %14d %12s"
      % ("TOTAL", len(rows), sum(1 for r in rows if r["shortest"]), "n/a"))
print("\n=== VS MATEFISH ENDED ===", flush=True)
