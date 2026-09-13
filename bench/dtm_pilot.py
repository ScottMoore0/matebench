#!/usr/bin/env python3
"""Tablebase positions as a benchmark corpus -- a pilot on the tables at hand.

docs/HELDOUT.md wants a corpus whose terms permit anything and whose depths are
exact. A DTM tablebase gives exact distance to mate with no search, and positions
generated here are ours to redistribute. The generated retrograde corpus failed on
yield (0.5% at d13-17) because exact minimality needs an absence proof; a
tablebase has that proof precomputed.

The question to answer before building anything is BIAS. Endgames with three or
four pieces are not composed problems, and an engine could rank very differently
on them. So the pilot measures each engine on the tablebase set AND on ChestUCI
positions of the same depths, and compares how they rank on each. It uses the
3-4 man Gaviota tables present locally. The 2026-09-13 run reversed the ranking of
every engine measured, which settles the pool question without the 5-man set;
5-man tables would matter only for building a separate endgame track.

  generate  sample positions per material and depth band, probe DTM, write EPD
  check     MateProver --iterative-depth must report exactly the tablebase depth
  prove     MateProver, finding track (--direct-depth, node budget) over a corpus
  report    per-band solve rates on both corpora, and the paired ranking on each

Gaviota convention, checked on 4,000 random legal KQvK positions: DTM in plies,
positive when the side to move mates, 1 meaning mate in 1. Mate in N is therefore
(dtm + 1) // 2. An illegal position (the side not to move in check) probes as 0.
"""
import argparse
import json
import random
import re
import subprocess
from math import comb
from pathlib import Path

import config  # paths: see bench/config.py

BANDS = [(10, 13), (14, 17), (18, 21), (22, 999)]
PIECE = {"K": 6, "Q": 5, "R": 4, "B": 3, "N": 2}
BM = re.compile(r"\bbm\s+#(\d+)")
DM = re.compile(r"; dm (\d+)")


def band_of(n):
    for lo, hi in BANDS:
        if lo <= n <= hi:
            return (lo, hi)
    return None


def fen4(line):
    return " ".join(line.split(";")[0].split(" bm ")[0].split()[:4])


def sign_p(w, l):
    n = w + l
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0


def generate(a):
    import chess
    import chess.gaviota
    tb = chess.gaviota.open_tablebase(a.gaviota)
    rng = random.Random(a.seed)
    lines = []
    for sig in a.configs.split(","):
        attacker, defender = sig.split("v")
        pieces = [(PIECE[c], chess.WHITE) for c in attacker] + [(PIECE[c], chess.BLACK) for c in defender]
        got = {b: [] for b in BANDS}
        seen = set()
        for _ in range(a.tries):
            if all(len(v) >= a.per_band for v in got.values()):
                break
            squares = rng.sample(range(64), len(pieces))
            board = chess.Board(None)
            for (ptype, colour), sq in zip(pieces, squares):
                board.set_piece_at(sq, chess.Piece(ptype, colour))
            board.turn = chess.WHITE
            if rng.random() < 0.5:        # half the set has Black as the mating side
                board = board.mirror()
            if not board.is_valid():
                continue
            key = board.epd()
            if key in seen:
                continue
            seen.add(key)
            dtm = tb.probe_dtm(board)
            if dtm <= 0:
                continue
            n = (dtm + 1) // 2
            b = band_of(n)
            if b is None or len(got[b]) >= a.per_band:
                continue
            got[b].append('%s bm #%d; c0 "%s dtm %d";' % (key, n, sig, dtm))
        print("  %-6s %s" % (sig, "  ".join("d%d-%s %d" % (lo, hi if hi < 999 else "+", len(v))
                                          for (lo, hi), v in got.items())), flush=True)
        for v in got.values():
            lines.extend(v)
    out = config.corpus(a.out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("  wrote %d positions to %s" % (len(lines), out))


def run_engine(engine, lines, flags, nodes, par):
    cmd = [engine] + flags + ["--threads", "1", "--parallel-positions", str(par), "--node-limit", str(nodes), "-"]
    text = "".join("%s bm #%s;\n" % (fen4(l), BM.search(l).group(1)) for l in lines)
    out = subprocess.run(cmd, input=text, capture_output=True, text=True, errors="replace").stdout.splitlines()
    if len(out) != len(lines):
        raise SystemExit("engine returned %d lines for %d positions" % (len(out), len(lines)))
    return out


def corpus_lines(name, lo, hi):
    keep = []
    for l in config.corpus(name).read_text(encoding="utf-8", errors="replace").splitlines():
        m = BM.search(l)
        if m and not l.startswith("%") and lo <= int(m.group(1)) <= hi:
            keep.append(l)
    return keep


def check(a):
    lines = corpus_lines(a.corpus, 1, 999)
    sample = random.Random(a.seed).sample(lines, min(a.n, len(lines)))
    out = run_engine(a.engine, sample, ["--iterative-depth", "--no-portfolio"], a.nodes, a.jobs)
    exact = shorter = longer = timeout = 0
    for l, r in zip(sample, out):
        want = int(BM.search(l).group(1))
        m = DM.search(r)
        if not m:
            timeout += 1
        elif int(m.group(1)) == want:
            exact += 1
        elif int(m.group(1)) < want:
            shorter += 1
            print("  SHORTER than the tablebase: %s  tb %d  engine %s" % (fen4(l), want, m.group(1)))
        else:
            longer += 1
            print("  LONGER than the tablebase:  %s  tb %d  engine %s" % (fen4(l), want, m.group(1)))
    print("  check: %d positions -- exact %d, engine shorter %d, engine longer %d, timeout %d"
          % (len(sample), exact, shorter, longer, timeout))


def prove(a):
    lines = corpus_lines(a.corpus, a.min_depth, a.max_depth)
    state_path = Path(config.results("dtm_pilot_state.json"))
    st = json.loads(state_path.read_text()) if state_path.exists() else {}
    tag = "mateprover|direct|%d" % a.nodes
    todo = [l for l in lines if "%s|%s" % (fen4(l), tag) not in st]
    print("  %s d%d-%s: %d positions, %d to run" % (a.corpus, a.min_depth, a.max_depth, len(lines), len(todo)), flush=True)
    for i in range(0, len(todo), 256):
        chunk = todo[i:i + 256]
        for l, r in zip(chunk, run_engine(a.engine, chunk, ["--direct-depth"], a.nodes, a.jobs)):
            want = int(BM.search(l).group(1))
            m = DM.search(r)
            st["%s|%s" % (fen4(l), tag)] = {"dm": int(m.group(1)) if m and int(m.group(1)) <= want else None}
        state_path.write_text(json.dumps(st))
        print("     %d/%d" % (min(i + 256, len(todo)), len(todo)), flush=True)


def report(a):
    mp = json.loads(Path(config.results("dtm_pilot_state.json")).read_text())
    sf = json.loads(Path(config.results("vs_stockfish_state.json")).read_text())
    mp_tag = "mateprover|direct|%d" % a.nodes
    mh_tag = "%s|%d" % (a.arm, a.mh_nodes)
    for name in (a.corpus, a.compare):
        lines = corpus_lines(name, BANDS[0][0], 999)
        print("\n  %s -- MateProver --direct-depth %s nodes against %s %s nodes"
              % (name, "{:,}".format(a.nodes), a.arm, "{:,}".format(a.mh_nodes)))
        print("  %-8s %5s %8s %8s %8s %8s %8s" % ("band", "n", "prover", "hunter", "p only", "h only", "p"))
        W = L = N = P = H = 0
        for lo, hi in BANDS:
            cases = [fen4(l) for l in lines if lo <= int(BM.search(l).group(1)) <= hi]
            cases = [f for f in cases if "%s|%s" % (f, mp_tag) in mp and "%s|%s" % (f, mh_tag) in sf]
            if not cases:
                continue
            p = {f for f in cases if mp["%s|%s" % (f, mp_tag)]["dm"]}
            h = {f for f in cases if sf["%s|%s" % (f, mh_tag)]["dm"]}
            w, l_ = len(p - h), len(h - p)
            W, L, N, P, H = W + w, L + l_, N + len(cases), P + len(p), H + len(h)
            print("  d%-2d-%-4s %5d %8d %8d %8d %8d %8.4f" % (lo, hi if hi < 999 else "+", len(cases), len(p), len(h), w, l_, sign_p(w, l_)))
        if N:
            print("  %-8s %5d %8d %8d %8d %8d %8.4f" % ("ALL", N, P, H, W, L, sign_p(W, L)))
            print("  solve rate: prover %.1f%%, hunter %.1f%%" % (100.0 * P / N, 100.0 * H / N))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
g = sub.add_parser("generate")
g.add_argument("--gaviota", required=True)
g.add_argument("--configs", default="KQvKR,KBBvK,KRvKR,KQvKQ,KRvK,KQvK")
g.add_argument("--per-band", type=int, default=40)
g.add_argument("--tries", type=int, default=400_000)
g.add_argument("--seed", default="dtm-pilot")
g.add_argument("--out", default="dtm_pilot.epd")
for name in ("check", "prove"):
    s = sub.add_parser(name)
    s.add_argument("--engine", required=True, help="path to a mateprover binary")
    s.add_argument("--corpus", default="dtm_pilot.epd")
    s.add_argument("--nodes", type=int, default=4_000_000 if name == "prove" else 64_000_000)
    s.add_argument("--jobs", type=int, default=12)
    s.add_argument("--seed", default="dtm-pilot-check")
    s.add_argument("--n", type=int, default=40)
    s.add_argument("--min-depth", type=int, default=10)
    s.add_argument("--max-depth", type=int, default=999)
r = sub.add_parser("report")
r.add_argument("--corpus", default="dtm_pilot.epd")
r.add_argument("--compare", default="chestuci.epd")
r.add_argument("--nodes", type=int, default=4_000_000)
r.add_argument("--arm", default="mh19-null")
r.add_argument("--mh-nodes", type=int, default=10_000_000)
a = ap.parse_args()
{"generate": generate, "check": check, "prove": prove, "report": report}[a.cmd](a)
