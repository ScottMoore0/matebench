#!/usr/bin/env python3
"""What should the finder lane's verify budget be? 4M was a guess.

The generate-and-verify run reported 41 claims, 24 verified, 17 REJECTED at a
4,000,000-node verification budget. A rejected claim is either false - the
finder over-claiming, which is the flaw this lane exists to catch - or true but
unverified within the budget. Those need completely different responses, and
the run as measured cannot tell them apart.

DESIGN. The obvious sweep (verify every claim at 1M, 2M, 4M, ...) does five
searches per claim to learn one number. Instead, run each verification ONCE at
a large budget and record the nodes it actually consumed (`acn`). A
deterministic, single-threaded --direct-depth search with a node limit is the
same search either way; the limit only says when to give up. So a verification
that completes in `acn` nodes would also complete at any budget >= acn and at
none below it, and the whole curve is derivable from one run per claim.

That is an assumption about the engine, not a fact, and this project has been
burned by exactly that kind of unchecked reasoning. So PHASE C tests it: for a
sample of verified claims, re-run at acn (must succeed) and at acn-1 (must
fail). If the control does not hold, the derived curve is discarded and the
sweep has to be done the slow way.

Everything is checkpointed to JSON as it is produced. A killed run resumes
instead of losing hours - a lesson from a 3-hour scaling run that lost all of
its output.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pools import by_depth
import config  # paths: see bench/config.py

MP = str(config.ENGINES / "mateprover")
HUNT = str(config.ENGINES / "hunt18-clean")
DM = re.compile(r"\bdm (\d+)")
ACN = re.compile(r"\bacn (\d+)")
# Negative mate scores mean the side to move is BEING mated. Never abs() this.
MATE = re.compile(r"\bscore\s+mate\s+(-?\d+)")
# MateMode OFF: measured 2026-09-02 as the cause of MateHunter's deep deficit
# (+21 of 234 at d>=26 with it off, no band worse). See ENGINES.md.
OPTS = {"Threads": 1, "Hash": 256, "MateMode": "false", "MateEval": "true"}


def prove(fen, depth, mode, nodes):
    """Return (proved?, nodes consumed)."""
    p = subprocess.run(
        [MP, "-z", str(depth), mode, "--no-portfolio", "--threads", "1",
         "--node-limit", str(nodes), "-"],
        input="%s bm #%d;\n" % (fen, depth), capture_output=True, text=True,
        errors="replace", timeout=3600)
    out = p.stdout or ""
    acn = ACN.search(out)
    return bool(DM.search(out)), int(acn.group(1)) if acn else 0


def find(fen, depth, nodes):
    """The finder's claimed distance, or None. Not trusted."""
    p = subprocess.Popen([HUNT], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
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
           ["setoption name %s value %s" % kv for kv in OPTS.items()] + \
           ["isready", "ucinewgame", "position fen %s 0 1" % fen,
            "go mate %d nodes %d" % (depth, nodes)]
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
    best = None
    for l in lines:
        m = MATE.search(l)
        if m:
            v = int(m.group(1))
            if 0 < v <= depth:
                best = v if best is None else min(best, v)
    return best


def load(path):
    return json.loads(Path(path).read_text()) if os.path.exists(path) else {}


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1))


ap = argparse.ArgumentParser()
ap.add_argument("--depths", default="12,14,16,18")  # LINT-OK: ONE-BAND - four bands
ap.add_argument("--per-depth", type=int, default=10)
ap.add_argument("--prove-nodes", type=int, default=20_000_000)
ap.add_argument("--find-nodes", type=int, default=20_000_000)
ap.add_argument("--max-verify", type=int, default=32_000_000)
ap.add_argument("--control-n", type=int, default=6)
ap.add_argument("--control-select", choices=("cheap", "expensive", "spread"),
                default="spread",
                help="which verifications to control on. The first run used "
                     "'cheap' and so confirmed the derivation only where it "
                     "was never in doubt - the ceiling matters in the TAIL, "
                     "which is exactly where a cheap sample says nothing.")
ap.add_argument("--finder-matemode", choices=("false", "true"), default="false",
                help="the finder's MateMode. The published 2026-08-30 run used true; the "
                     "option was switched off on 2026-09-02, which changes 7 of its 39 claims")
# NOT /tmp: WSL wipes it when the distro idles, which destroyed one run's
# per-claim data after it had finished.
ap.add_argument("--state",
                default=config.results("verify_budget_state.json"))
a = ap.parse_args()

Path(a.state).parent.mkdir(parents=True, exist_ok=True)
OPTS["MateMode"] = a.finder_matemode
print("  finder hunt18-clean, MateMode=%s, MateEval=%s" % (OPTS["MateMode"], OPTS["MateEval"]), flush=True)
st = load(a.state)
st.setdefault("claims", {})     # fen -> {"depth","claim"}
st.setdefault("verify", {})     # fen -> {"ok","acn"}
st.setdefault("control", [])

# ---- Phase A: positions the prover cannot do alone, with a finder claim -----
cases = []
for d in [int(x) for x in a.depths.split(",")]:
    for c in by_depth(d, d, per_depth=a.per_depth, seed="vbudget"):
        cases.append((c["fen4"], d))
print("  phase A: %d positions, prover %s nodes, finder %s nodes"
      % (len(cases), "{:,}".format(a.prove_nodes), "{:,}".format(a.find_nodes)),
      flush=True)

solved_alone = 0
for fen, d in cases:
    if fen in st["claims"]:
        continue
    ok, _ = prove(fen, d, "--iterative-depth", a.prove_nodes)
    if ok:
        st["claims"][fen] = {"depth": d, "claim": None, "prover": True}
        save(a.state, st)
        continue
    k = find(fen, d, a.find_nodes)
    st["claims"][fen] = {"depth": d, "claim": k, "prover": False}
    save(a.state, st)

solved_alone = sum(1 for v in st["claims"].values() if v["prover"])
claims = {f: v for f, v in st["claims"].items()
          if not v["prover"] and v["claim"] is not None}
print("     prover solved alone %d/%d; finder claimed on %d of the %d missed"
      % (solved_alone, len(cases), len(claims), len(cases) - solved_alone),
      flush=True)

# ---- Phase B: verify each claim ONCE at a large budget, record acn ----------
print("\n  phase B: verifying %d claims at up to %s nodes"
      % (len(claims), "{:,}".format(a.max_verify)), flush=True)
for fen, v in claims.items():
    if fen in st["verify"]:
        continue
    ok, acn = prove(fen, v["claim"], "--direct-depth", a.max_verify)
    st["verify"][fen] = {"ok": ok, "acn": acn}
    save(a.state, st)

done = {f: st["verify"][f] for f in claims if f in st["verify"]}
verified = {f: r for f, r in done.items() if r["ok"]}
print("     %d/%d claims verified at the ceiling; %d refuted or unreachable"
      % (len(verified), len(done), len(done) - len(verified)), flush=True)

# ---- Phase C: is the derivation sound? -------------------------------------
print("\n  phase C: control - re-run at exactly acn (expect ok) and acn-1"
      " (expect fail)", flush=True)
ranked = [f for f in sorted(verified, key=lambda f: verified[f]["acn"])
          if verified[f]["acn"] > 1]
if a.control_select == "cheap":
    sample = ranked[:a.control_n]
elif a.control_select == "expensive":
    sample = ranked[-a.control_n:]
else:
    # Evenly spaced across the whole cost range, so the control covers the
    # cheap end AND the tail rather than one of them.
    if len(ranked) <= a.control_n:
        sample = ranked
    else:
        step = (len(ranked) - 1) / float(a.control_n - 1)
        sample = [ranked[int(round(i * step))] for i in range(a.control_n)]
print("     selecting %s: acn %s" % (
    a.control_select,
    ", ".join("{:,}".format(verified[f]["acn"]) for f in sample)), flush=True)
if not st["control"]:
    for fen in sample:
        acn = verified[fen]["acn"]
        k = claims[fen]["claim"]
        at, _ = prove(fen, k, "--direct-depth", acn)
        below, _ = prove(fen, k, "--direct-depth", acn - 1)
        st["control"].append({"acn": acn, "at": at, "below": below})
        save(a.state, st)
good = sum(1 for c in st["control"] if c["at"] and not c["below"])
for c in st["control"]:
    print("     acn %-10s at:%-5s below:%-5s %s"
          % ("{:,}".format(c["acn"]), c["at"], c["below"],
             "ok" if (c["at"] and not c["below"]) else "VIOLATION"))
sound = st["control"] and good == len(st["control"])
print("     control %d/%d consistent -> derived curve is %s"
      % (good, len(st["control"]), "usable" if sound else "NOT USABLE"),
      flush=True)

# ---- Phase D: the curve ----------------------------------------------------
print("\n  phase D: verified claims against budget"
      "  (base: prover alone %d/%d)" % (solved_alone, len(cases)), flush=True)
if not sound:
    print("     SKIPPED. The control failed, so acn does not determine the")
    print("     outcome at other budgets and this curve cannot be derived.")
else:
    grid = [1, 2, 4, 8, 16, 32]
    print("     %-12s %8s %10s %12s" % ("budget", "verified", "of claims", "total certified"))
    for g in grid:
        b = g * 1_000_000
        if b > a.max_verify:
            break
        n = sum(1 for r in verified.values() if r["acn"] <= b)
        print("     %-12s %8d %10d %12d"
              % ("{:,}".format(b), n, len(done), solved_alone + n))
    costs = sorted(r["acn"] for r in verified.values())
    if costs:
        mid = costs[len(costs) // 2]
        print("\n     median verification cost %s nodes; max %s"
              % ("{:,}".format(mid), "{:,}".format(costs[-1])))
        at4 = sum(1 for c in costs if c <= 4_000_000)
        print("     at the shipped 4,000,000 default: %d of %d verified claims"
              % (at4, len(costs)))
print("\n=== VERIFY BUDGET ENDED ===", flush=True)
