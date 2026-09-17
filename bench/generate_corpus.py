#!/usr/bin/env python3
"""Generate a mate corpus that no engine has been tuned on, by retrograde steps
from synthetic checkmates.

    python bench/generate_corpus.py --seed round-1 --out corpora/generated.epd
    python bench/matebench.py fetch generated        # record its checksum

Why it exists. Every public mate corpus is a candidate for tuning, and the two
used here overlap almost completely: 6,526 of ChestUCI's 6,545 positions are
also in matetrack, which MateHunter was tuned on. A held-out pool has to come
from somewhere no engine could have seen, and positions that did not exist
before this script ran qualify.

How. Seeds are random legal positions in which Black, to move, is checkmated,
drawn from a named random seed with no third-party data. From each level's
positions the generator steps back two moves with MateProver's
`--list-unmoves` (an attacker move retracted after a defender move), samples
the predecessors under the same seed, and asks MateProver for each candidate's
**shortest** mate (`--iterative-depth --no-portfolio`, node-limited, single
thread, deterministic). A candidate whose shortest mate is exactly the level's
depth becomes part of the next frontier; every candidate with a proved shortest
mate is written to the corpus with that depth.

Every run with the same arguments, corpus exclusions and MateProver build
produces the same file: sampling is seeded, candidates are processed in sorted
order, and the proofs are node-limited.

What it cannot avoid, stated in the metadata and in corpora/PROVENANCE.md:

  * Only positions MateProver proves within the node budget are kept, so the
    corpus is bounded by MateProver's reach. MateProver is the verifier, not a
    contestant on the finding track, but a generated corpus cannot measure
    MateProver's own reach.
  * Positions reached from random checkmates are not composed problems.
    Uncaptures add material as the walk goes back, but the deepest levels are
    still simpler than ChestUCI's, and the tablebase pilot showed that simple
    material can reverse an engine ranking. Report generated-corpus results
    under their own name.
  * Depth grows by one per level at a cost that rises with depth, so the corpus
    is shallow compared with ChestUCI.
"""
import argparse
import datetime
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chess

import config

# LINT-OK: ONE-BAND - this generates positions at every depth and measures nothing

PRED = re.compile(r"\[([^\]]+)\]")
DM = re.compile(r"; dm (\d+)")
PLACEABLE = "QRRBBNNNPPPPPP"


def fen4(board):
    return " ".join(board.fen().split()[:4])


def random_mate(rng, tries):
    """A legal position with Black to move and checkmated, or None."""
    for _ in range(tries):
        b = chess.Board(None)
        free = list(chess.SQUARES)
        rng.shuffle(free)
        b.set_piece_at(free.pop(), chess.Piece(chess.KING, chess.WHITE))
        b.set_piece_at(free.pop(), chess.Piece(chess.KING, chess.BLACK))
        for color, count in ((chess.WHITE, rng.randint(2, 5)), (chess.BLACK, rng.randint(1, 6))):
            for _ in range(count):
                symbol = rng.choice(PLACEABLE)
                piece = chess.Piece.from_symbol(symbol if color == chess.WHITE else symbol.lower())
                for i, sq in enumerate(free):
                    if piece.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                        continue
                    b.set_piece_at(free.pop(i), piece)
                    break
        b.turn = chess.BLACK
        b.castling_rights = chess.BB_EMPTY
        if b.is_valid() and reachable_material(b) and b.is_checkmate():
            return b
    return None


def run_chunks(argv, lines, jobs, timeout):
    """Run MateProver over `lines` in `jobs` parallel processes; the concatenated output lines."""
    if not lines:
        return []
    # Many small chunks, not one per worker: proof cost varies by orders of
    # magnitude between positions, and one chunk of hard ones would otherwise
    # hold a whole level on a single core while the others sit idle.
    size = max(1, (len(lines) + jobs * 16 - 1) // (jobs * 16))
    chunks = [lines[i:i + size] for i in range(0, len(lines), size)]

    def one(chunk):
        return subprocess.run(argv, input="\n".join(chunk) + "\n", capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout).stdout.splitlines()

    out = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(one, chunks):
            out.extend(part)
    return out


def predecessors(mp, fens, jobs):
    """{fen: [predecessor fen4, ...]} for defender-to-move or attacker-to-move positions."""
    result = {}
    for line in run_chunks(mp + ["--list-unmoves", "-"], fens, jobs, 3600):
        if "; unmoves " not in line:
            continue
        head = line.split(";", 1)[0].strip()
        result[head] = [" ".join(p.split()[:4]) for p in PRED.findall(line)]
    return result


def shortest(mp, fens, depth, nodes, jobs):
    """{fen: shortest mate proved within `depth` and `nodes`, or None}."""
    argv = mp + ["--iterative-depth", "--no-portfolio", "--threads", "1", "--node-limit", str(nodes),
                 "-z", str(depth), "-"]
    result = {}
    for line in run_chunks(argv, fens, jobs, 7200):
        if "; acn " not in line:
            continue
        head = line.split(";", 1)[0].strip()
        m = DM.search(line)
        result[head] = int(m.group(1)) if m else None
    return result


def reachable_material(board):
    """False when a side has more material than a game can produce.

    Uncaptures add pieces, and python-chess's validity check does not count
    them, so a walk back can reach positions such as two queens beside eight
    pawns. Stockfish refuses those outright. A side may have at most 16 pieces,
    and every piece beyond the starting set must be a promotion, paid for by a
    missing pawn.
    """
    for color in (chess.WHITE, chess.BLACK):
        count = lambda piece_type: len(board.pieces(piece_type, color))
        promoted = (max(0, count(chess.QUEEN) - 1) + max(0, count(chess.ROOK) - 2)
                    + max(0, count(chess.BISHOP) - 2) + max(0, count(chess.KNIGHT) - 2))
        if count(chess.PAWN) + promoted > 8 or bin(board.occupied_co[color]).count("1") > 16:
            return False
    return True


def legal_attacker_to_move(fen):
    try:
        b = chess.Board(fen + " 0 1")
    except ValueError:
        return False
    return b.is_valid() and reachable_material(b) and not b.is_game_over()


def excluded_fens(names):
    out = set()
    for name in names:
        path = config.corpus(name)
        if not path.exists():
            sys.exit("exclusion corpus %s not found in %s; fetch it first, or the corpus cannot be "
                     "shown to be disjoint from it" % (name, config.CORPORA))
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if line.strip() and not line.startswith("%"):
                out.add(" ".join(line.split(";")[0].split(" bm ")[0].split()[:4]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", required=True, help="names every random choice; the same seed gives the same corpus")
    ap.add_argument("--out", default=str(config.corpus("generated.epd")))
    ap.add_argument("--seeds", type=int, default=60, help="synthetic checkmates to start from")
    ap.add_argument("--max-depth", type=int, default=16)
    ap.add_argument("--frontier", type=int, default=400, help="positions kept at each level to step back from")
    ap.add_argument("--candidates", type=int, default=2400, help="candidates proved at each level")
    ap.add_argument("--per-position", type=int, default=6, help="predecessors sampled per position per step")
    ap.add_argument("--nodes", type=int, default=4_000_000, help="MateProver node budget per proof")
    ap.add_argument("--exclude", nargs="*", default=["matetrack.epd", "chestuci.epd"],
                    help="corpora the output must be disjoint from")
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--max-minutes", type=float, default=0, help="stop after the level that passes this; 0 = no limit")
    ap.add_argument("--start", default="",
                    help="continue from an existing corpus instead of synthetic checkmates: its positions with "
                         "bm #<start-depth> are the first frontier, and the walk goes deeper from there")
    ap.add_argument("--start-depth", type=int, default=0)
    a = ap.parse_args(argv)
    if bool(a.start) != bool(a.start_depth):
        sys.exit("--start and --start-depth go together")

    mp = config.mateprover()
    version = subprocess.run(mp + ["--version"], capture_output=True, text=True).stdout.strip()
    rng = random.Random(a.seed)
    exclude = excluded_fens(a.exclude)
    started = time.monotonic()
    print("generating from seed %r with %s; excluding %d positions from %s"
          % (a.seed, version, len(exclude), ", ".join(a.exclude)), flush=True)

    corpus = {}                      # fen -> proved shortest mate
    levels = []

    def step_back(exact):
        """Defender-to-move frontier: one retracted defender move back from `exact`."""
        exact = list(exact)
        rng.shuffle(exact)
        back = predecessors(mp, sorted(exact[:a.frontier]), a.jobs)
        nxt = []
        for fen in sorted(back):
            options = sorted(set(back[fen]) - seen)
            rng.shuffle(options)
            nxt.extend(options[:a.per_position])
        found = sorted({f for f in nxt if chess.Board(f + " 0 1").is_valid()
                        and reachable_material(chess.Board(f + " 0 1"))})
        rng.shuffle(found)
        found = sorted(found[:a.frontier])
        seen.update(found)
        return found

    start_info = None
    if a.start:
        # Continue deeper from an existing corpus. Every position already in it
        # counts as seen, so the output holds only positions it does not.
        rows = []
        for line in Path(a.start).read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = re.search(r"\bbm\s+#(\d+)", line)
            if m and not line.startswith("%"):
                rows.append((" ".join(line.split(";")[0].split(" bm ")[0].split()[:4]), int(m.group(1))))
        exact0 = sorted(f for f, d in rows if d == a.start_depth)
        if not exact0:
            sys.exit("%s has no positions at bm #%d" % (a.start, a.start_depth))
        seen = {f for f, _ in rows} | exclude
        start_info = {"file": Path(a.start).name, "sha256": hashlib.sha256(Path(a.start).read_bytes()).hexdigest(),
                      "depth": a.start_depth, "positions": len(exact0)}
        print("  continuing from %d positions at mate in %d in %s" % (len(exact0), a.start_depth, a.start),
              flush=True)
        frontier = step_back(exact0)
        first_depth = a.start_depth + 1
    else:
        seeds = []
        while len(seeds) < a.seeds:
            b = random_mate(rng, 200_000)
            if b is None:
                sys.exit("no checkmate found in 200,000 random placements")
            if fen4(b) not in exclude and fen4(b) not in seeds:
                seeds.append(fen4(b))
        print("  %d synthetic checkmates" % len(seeds), flush=True)
        seen = set(seeds) | exclude
        frontier = sorted(seeds)     # defender-to-move positions to step back from
        first_depth = 1

    for depth in range(first_depth, a.max_depth + 1):
        # A level costs roughly three times the one before it. Stop before one
        # that would run past the limit, not after it has.
        if a.max_minutes and levels:
            projected = (time.monotonic() - started) + 3.5 * levels[-1]["seconds"]
            if projected / 60.0 > a.max_minutes:
                print("  stopping before depth %d: projected to pass the %.0f-minute limit"
                      % (depth, a.max_minutes), flush=True)
                break
        t0 = time.monotonic()
        # Attacker-to-move candidates: one retracted move back from the frontier.
        preds = predecessors(mp, frontier, a.jobs)
        pool = []
        for fen in frontier:
            options = sorted(set(preds.get(fen, [])) - seen)
            rng.shuffle(options)
            pool.extend(options[:a.per_position])
        pool = sorted({f for f in pool if legal_attacker_to_move(f)})
        rng.shuffle(pool)
        candidates = sorted(pool[:a.candidates])
        seen.update(candidates)
        proved = shortest(mp, candidates, depth, a.nodes, a.jobs)
        exact = sorted(f for f in candidates if proved.get(f) == depth)
        for f in candidates:
            if proved.get(f):
                corpus[f] = proved[f]
        unproved = sum(1 for f in candidates if proved.get(f) is None)
        levels.append({"depth": depth, "frontier": len(frontier), "candidates": len(candidates),
                       "exact": len(exact), "shorter": len(candidates) - len(exact) - unproved,
                       "unproved": unproved, "seconds": round(time.monotonic() - t0, 1)})
        print("  depth %2d: frontier %4d, candidates %4d, shortest mate exactly %d: %4d, shorter %4d, "
              "unproved %4d  (%.0f s)" % (depth, len(frontier), len(candidates), depth, len(exact),
                                          levels[-1]["shorter"], unproved, levels[-1]["seconds"]), flush=True)
        if not exact or depth == a.max_depth:
            break
        frontier = step_back(exact)
        if not frontier:
            break
        if a.max_minutes and (time.monotonic() - started) / 60.0 > a.max_minutes:
            print("  stopping: time limit reached", flush=True)
            break

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(corpus.items(), key=lambda kv: (kv[1], kv[0]))
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for i, (fen, dm) in enumerate(rows):
            ident = hashlib.sha256(("%s|%s" % (a.seed, fen)).encode()).hexdigest()[:12]
            fh.write('%s bm #%d; id "gen-%s";\n' % (fen, dm, ident))
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    bands = {}
    for _, dm in rows:
        bands[dm] = bands.get(dm, 0) + 1
    meta = {
        "file": out.name, "sha256": digest, "positions": len(rows),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "seed": a.seed, "synthetic_checkmates": a.seeds, "max_depth": a.max_depth, "frontier": a.frontier,
        "candidates_per_level": a.candidates, "per_position": a.per_position, "nodes_per_proof": a.nodes,
        "excluded": {name: sha for name, sha in
                     ((n, hashlib.sha256(config.corpus(n).read_bytes()).hexdigest()) for n in a.exclude)},
        "mateprover": version, "start": start_info, "levels": levels, "positions_by_depth": {str(k): v for k, v in sorted(bands.items())},
        "limits": ["only positions MateProver proves within nodes_per_proof are kept",
                   "positions descend from random checkmates, not composed problems",
                   "report results on this corpus under its own name"],
    }
    # LF on every platform: the metadata is hashed into a round's commitment, and a
    # file written with CRLF on Windows hashes differently once git stores it with LF.
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote %d positions to %s, sha256 %s" % (len(rows), Path(out).name, digest))
    print("  by depth: " + ", ".join("d%d %d" % (k, v) for k, v in sorted(bands.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
