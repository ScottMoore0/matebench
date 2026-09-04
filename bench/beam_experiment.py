#!/usr/bin/env python3
"""Does pruning DEFENDER replies find mates the exhaustive finder cannot?

The one lever left that attacks the exponent: at every defender node keep only
the first K replies in the engine's own ordering (--beam-defender K, in
prove_defender). It is UNSOUND - on a known mate-in-4 it reported mate in 3 -
so every claim it makes is re-proved by a plain --direct-depth search before it
counts. The bar it must clear is the one the finder lane failed: at EQUAL node
budget, find verified mates the exhaustive search does not.

Paired, node-budgeted, one thread, no portfolio, on ChestUCI (a corpus nothing
here was tuned on). Reported per band with discordant pairs and a sign test.
A beam claim of dm < N that fails verification is a FALSE claim and is counted
as such, separately from "unconfirmed within the verification budget".
"""
import argparse, json, random, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

MP = str(Path.home() / "mp_beam_build" / "mateprover")
EPD = config.corpus("chestuci.epd")
BM = re.compile("bm #([0-9]+)"); DM = re.compile("dm ([0-9]+)"); PRUNED = re.compile("beam [0-9]+ (pruned|complete)")


def run(fen, depth, nodes, beam=0):
    argv = [MP, "-z", str(depth), "--direct-depth", "--no-portfolio", "--threads", "1", "--node-limit", str(nodes)]
    if beam: argv += ["--beam-defender", str(beam)]
    p = subprocess.run(argv + ["-"], input="%s bm #%d;" % (fen, depth) + chr(10), capture_output=True, text=True, errors="replace", timeout=3600)
    out = p.stdout or ""; m = DM.search(out); pr = PRUNED.search(out)
    return {"dm": int(m.group(1)) if m else None, "pruned": (pr.group(1) if pr else None)}


ap = argparse.ArgumentParser()
ap.add_argument("--n-per-band", type=int, default=25)
ap.add_argument("--nodes", type=int, default=20_000_000)
ap.add_argument("--verify-nodes", type=int, default=50_000_000)
ap.add_argument("--beams", default="2,3,5")  # LINT-OK: ONE-BAND - four bands below
ap.add_argument("--jobs", type=int, default=8)
ap.add_argument("--state", default=config.results("beam_experiment_state.json"))
a = ap.parse_args()
st = json.loads(Path(a.state).read_text()) if Path(a.state).exists() else {}
BANDS = [(14, 17), (18, 21), (22, 25), (26, 40)]
pool = {}
for line in EPD.read_text(encoding="utf-8", errors="replace").splitlines():
    m = BM.search(line)
    if not m or line.startswith("%"): continue
    d = int(m.group(1)); fen = " ".join(line.split(" bm ")[0].split()[:4])
    for lo, hi in BANDS:
        if lo <= d <= hi: pool.setdefault((lo, hi), []).append((fen, d))
rng = random.Random("beam-experiment"); cases = []
for b in BANDS:
    rng.shuffle(pool[b]); cases += pool[b][:a.n_per_band]
beams = [int(x) for x in a.beams.split(",")]
print("  %d positions (%d per band), %s nodes, beams %s, verify %s nodes" % (len(cases), a.n_per_band, "{:,}".format(a.nodes), beams, "{:,}".format(a.verify_nodes)), flush=True)

# phase 1: plain and beam arms, paired
jobs = [(f, d, k) for f, d in cases for k in [0] + beams if "%s|%d" % (f, k) not in st]
def work(j):
    f, d, k = j; return "%s|%d" % (f, k), dict(run(f, d, a.nodes, k), depth=d)
done = 0
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    for key, v in ex.map(work, jobs):
        st[key] = v; done += 1
        if done % 25 == 0: Path(a.state).write_text(json.dumps(st)); print("     arms %d/%d" % (done, len(jobs)), flush=True)
Path(a.state).write_text(json.dumps(st))

# phase 2: verify every beam claim that the plain arm did not already establish at the same dm
vjobs = []
for f, d in cases:
    plain = st["%s|0" % f]["dm"]
    for k in beams:
        c = st["%s|%d" % (f, k)]["dm"]
        if c and not (plain and plain <= c) and "%s|v%d" % (f, c) not in st:
            vjobs.append((f, c))
vjobs = sorted(set(vjobs))
print("  verifying %d distinct beam claims at %s nodes" % (len(vjobs), "{:,}".format(a.verify_nodes)), flush=True)
def vwork(j):
    f, c = j; return "%s|v%d" % (f, c), run(f, c, a.verify_nodes)["dm"] is not None
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    for key, ok in ex.map(vwork, vjobs): st[key] = ok
Path(a.state).write_text(json.dumps(st))

def verified(f, k):
    """a beam claim counts if the plain arm reached that dm or better, or verification re-proved it"""
    c = st["%s|%d" % (f, k)]["dm"]; plain = st["%s|0" % f]["dm"]
    if not c: return None
    if plain and plain <= c: return True
    return st.get("%s|v%d" % (f, c), False)

for k in beams:
    print("\n  beam K=%d vs plain --direct-depth, both %s nodes" % (k, "{:,}".format(a.nodes)))
    print("  %-8s %4s %6s %8s %9s %9s %9s %9s %7s" % ("band", "n", "plain", "beam-clm", "beam-VER", "beam only", "plain only", "FALSE", "p"))
    W = L = 0
    for lo, hi in BANDS:
        g = [(f, d) for f, d in cases if lo <= d <= hi]
        plain = {f for f, _ in g if st["%s|0" % f]["dm"]}
        claimed = {f for f, _ in g if st["%s|%d" % (f, k)]["dm"]}
        ver = {f for f, _ in g if verified(f, k)}
        false = sum(1 for f, _ in g if st["%s|%d" % (f, k)]["dm"] and verified(f, k) is False and st["%s|%d" % (f, k)]["dm"] < d)
        w, l = len(ver - plain), len(plain - ver); n = w + l; W += w; L += l
        p = min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0
        print("  d%-2d-%-3d %4d %6d %8d %9d %9d %9d %9d %7.3f" % (lo, hi, len(g), len(plain), len(claimed), len(ver), w, l, false, p))
    n = W + L; p = min(1.0, 2 * sum(comb(n, i) for i in range(min(W, L) + 1)) / 2 ** n) if n else 1.0
    print("  %-8s discordant %d: beam-verified-only +%d / plain-only -%d   p = %.4f  -> %s" % ("ALL", n, W, L, p, "NOT established" if p > 0.05 else ("BEAM AHEAD" if W > L else "PLAIN AHEAD")))
print("\n  'FALSE' = a beam claim SHORTER than the stipulated depth that a %s-node plain search refuted." % "{:,}".format(a.verify_nodes))
print("  A claim at the stipulated depth that did not verify is unconfirmed, not false, and is simply not counted.")
print("=== BEAM EXPERIMENT ENDED ===", flush=True)
