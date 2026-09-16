#!/usr/bin/env python3
"""Tests for bench/absence.py and bench/certify.py.

    MATEBENCH_MATEPROVER_REPO=/path/to/mateprover python bench/test_certify.py

Certificates are built here by exhaustive search on small positions, so every
genuine certificate really is one and every expected verdict is exact. Each
forgery is a genuine certificate with one thing changed, so a rejection can only
come from that change. MateProver's checker is used for the mate half of a
minimality certificate.
"""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import absence   # noqa: E402
import certify   # noqa: E402

M1A = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - -"
M2A = "7k/8/5K2/8/8/8/8/6R1 w - -"
M2WIDE = "7k/8/5K2/8/8/p7/8/6R1 w - -"
NOMATE = "7k/7p/8/8/8/8/8/K5R1 w - -"      # no mate within 3, by exhaustive search

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print("  %s  %s%s" % ("ok  " if condition else "FAIL", name, ("  (%s)" % detail) if detail and not condition else ""))


def mate_certificate(board, n):
    """MateProver v1: a forced mate within n, or None."""
    for mv in list(board.legal_moves):
        board.push(mv)
        if board.is_checkmate():
            board.pop()
            return {"a": mv.uci(), "mate": True}
        if n > 1 and not board.is_game_over():
            replies = []
            for r in list(board.legal_moves):
                board.push(r)
                sub = mate_certificate(board, n - 1)
                board.pop()
                if sub is None:
                    replies = None
                    break
                replies.append({"r": r.uci(), "p": sub})
            if replies:
                board.pop()
                return {"a": mv.uci(), "d": replies}
        board.pop()
    return None


def absence_node(board, j):
    """matebench-absence-1 node: no mate within j, or None if there is one."""
    entries = []
    for mv in list(board.legal_moves):
        board.push(mv)
        try:
            if board.is_checkmate():
                return None
            if j == 1 or not any(True for _ in board.legal_moves):
                entries.append({"a": mv.uci()})
                continue
            found = None
            for r in list(board.legal_moves):
                board.push(r)
                sub = absence_node(board, j - 1)
                board.pop()
                if sub is not None:
                    found = {"a": mv.uci(), "r": r.uci(), "p": sub}
                    break
            if found is None:
                return None
            entries.append(found)
        finally:
            board.pop()
    return {"m": entries}


def shortest(fen, cap=3):
    for n in range(1, cap + 1):
        if mate_certificate(chess.Board(fen + " 0 1"), n) is not None:
            return n
    return None


def absence_cert(fen, k):
    node = absence_node(chess.Board(fen + " 0 1"), k)
    return None if node is None else {"format": absence.ABSENCE, "k": k, "proof": node}


def minimality_cert(fen):
    n = shortest(fen)
    return {"format": absence.MINIMALITY, "n": n, "mate": mate_certificate(chess.Board(fen + " 0 1"), n),
            "no_shorter": absence_cert(fen, n - 1) if n > 1 else None}


def rejected(kind, fen, n, cert, fragment):
    verdict, reason = absence.check(kind, fen, n, cert)
    return verdict == "rejected" and fragment in reason, reason


def test_absence():
    print("\nabsence certificates")
    for fen, k in ((NOMATE, 1), (NOMATE, 2), (NOMATE, 3), (M2A, 1), (M2WIDE, 1)):
        cert = absence_cert(fen, k)
        check("genuine: no mate within %d in %s" % (k, fen), cert is not None and
              absence.check("absence", fen, k, cert) == ("verified", ""), absence.check("absence", fen, k, cert or {}))
    check("the builder finds no absence certificate where a mate exists", absence_cert(M2A, 2) is None)

    base = absence_cert(M2A, 1)
    forged = copy.deepcopy(base)
    forged["k"] = 2
    ok, why = rejected("absence", M2A, 2, forged, "a defence must be given")
    check("a depth-1 certificate relabelled as depth 2 is rejected", ok, why)

    forged = copy.deepcopy(absence_cert(NOMATE, 2))
    del forged["proof"]["m"][0]
    ok, why = rejected("absence", NOMATE, 2, forged, "not refuted")
    check("an attacker move left unrefuted is rejected", ok, why)

    board = chess.Board(M1A + " 0 1")
    leaves = {"format": absence.ABSENCE, "k": 1, "proof": {"m": [{"a": m.uci()} for m in board.legal_moves]}}
    ok, why = rejected("absence", M1A, 1, leaves, "this move mates")
    check("a mating move passed off as a leaf is rejected", ok, why)

    forged = copy.deepcopy(absence_cert(NOMATE, 2))
    entry = next(e for e in forged["proof"]["m"] if "r" in e)
    entry["r"] = "a1a8"
    ok, why = rejected("absence", NOMATE, 2, forged, "illegal defender move")
    check("an illegal defence is rejected", ok, why)

    forged = copy.deepcopy(absence_cert(NOMATE, 1))
    genuine2 = absence_cert(NOMATE, 2)
    forged["proof"]["m"][0] = next(e for e in genuine2["proof"]["m"] if "r" in e and e["a"] == forged["proof"]["m"][0]["a"]) \
        if any("r" in e and e["a"] == forged["proof"]["m"][0]["a"] for e in genuine2["proof"]["m"]) else \
        dict(forged["proof"]["m"][0], r="h8g8", p={"m": []})
    ok, why = rejected("absence", NOMATE, 1, forged, "no attacker move left")
    check("a defence given with no attacker move left is rejected", ok, why)

    ok, why = rejected("absence", NOMATE, 3, absence_cert(NOMATE, 2), "the claim is k = 3")
    check("a certificate for another k is rejected", ok, why)
    ok, why = rejected("absence", NOMATE, 2, {"format": "something-else", "k": 2, "proof": {}}, "not a")
    check("a certificate in another format is rejected", ok, why)


def test_references():
    print("\nshared nodes")
    cert = absence_cert(NOMATE, 2)
    shared = copy.deepcopy(cert)
    entry = next(e for e in shared["proof"]["m"] if "r" in e)
    shared["nodes"] = {"s": entry["p"]}
    entry["p"] = {"ref": "s"}
    check("a sub-proof moved to a shared node still verifies",
          absence.check("absence", NOMATE, 2, shared) == ("verified", ""), absence.check("absence", NOMATE, 2, shared))

    elsewhere = {"format": absence.ABSENCE, "k": 1, "proof": {"ref": "root"},
                 "nodes": {"root": absence_cert(NOMATE, 1)["proof"]}}
    ok, why = rejected("absence", M2WIDE, 1, elsewhere, "")
    check("a shared node valid in one position is rejected in another", ok, why)
    ok, why = rejected("absence", NOMATE, 1, {"format": absence.ABSENCE, "k": 1, "proof": {"ref": "nope"}}, "names no shared node")
    check("a reference to a missing node is rejected", ok, why)
    loop = {"format": absence.ABSENCE, "k": 1, "proof": {"ref": "x"}, "nodes": {"x": {"ref": "x"}}}
    ok, why = rejected("absence", NOMATE, 1, loop, "")
    check("a reference cycle is rejected, not a hang", ok, why)


def test_minimality():
    print("\nminimality certificates")
    for fen in (M1A, M2A, M2WIDE):
        cert = minimality_cert(fen)
        check("genuine: shortest mate %d in %s" % (cert["n"], fen),
              absence.check("minimality", fen, cert["n"], cert) == ("verified", ""),
              absence.check("minimality", fen, cert["n"], cert))
    cert = minimality_cert(M2A)
    forged = dict(cert, no_shorter=None)
    ok, why = rejected("minimality", M2A, 2, forged, "no absence half")
    check("a mate with nothing showing no shorter mate is rejected", ok, why)
    forged = dict(cert, n=3, no_shorter=None)
    ok, why = rejected("minimality", M2A, 3, forged, "mate half")
    check("a mate half of the wrong depth is rejected", ok, why)
    forged = dict(minimality_cert(M1A), no_shorter=absence_cert(NOMATE, 1))
    ok, why = rejected("minimality", M1A, 1, forged, "needs no absence half")
    check("a mate in one with an absence half is rejected", ok, why)
    forged = dict(cert, no_shorter=absence_cert(NOMATE, 1))
    ok, why = rejected("minimality", M2A, 2, forged, "absence half")
    check("an absence half about another position is rejected", ok, why)


def test_certify_tool():
    print("\ncertify")
    tmp = Path(tempfile.mkdtemp(prefix="matebench-certify-"))
    try:
        positions = tmp / "round.epd"
        positions.write_text("%s bm #1;\n%s bm #3;\n%s bm #2;\n%s bm #4;\n" % (M1A, M2A, M2WIDE, NOMATE), encoding="utf-8")
        forged = minimality_cert(M2WIDE)
        forged["no_shorter"]["proof"]["m"].pop()
        a_lines = [
            {"fen": M1A, "claim": "minimality", "n": 1, "certificate": minimality_cert(M1A)},
            {"fen": M2A, "claim": "minimality", "n": 2, "certificate": minimality_cert(M2A)},
            {"fen": M2WIDE, "claim": "minimality", "n": 2, "certificate": forged},
            {"fen": NOMATE, "claim": "absence", "n": 3, "certificate": absence_cert(NOMATE, 3)},
            {"fen": NOMATE, "claim": "minimality", "n": 4},
            {"fen": "8/8/8/8/8/8/8/K1k5 w - -", "claim": "absence", "n": 1,
             "certificate": absence_cert("8/8/8/8/8/8/8/K1k5 w - -", 1)},
        ]
        b_lines = [{"fen": M1A, "claim": "minimality", "n": 1, "certificate": minimality_cert(M1A)}]
        a_file, b_file = tmp / "entrant.jsonl", tmp / "reference.jsonl"
        a_file.write_text("".join(json.dumps(x) + "\n" for x in a_lines) + "not json\n", encoding="utf-8")
        b_file.write_text("".join(json.dumps(x) + "\n" for x in b_lines), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            certify.main([str(a_file), "--against", str(b_file), "--positions", str(positions)])
        out = buf.getvalue()
        check("minimality: 2 verified, 1 rejected, 1 uncertified",
              "minimality claims     4, verified     2, rejected     1, uncertified     1" in out, out[:1500])
        check("absence: a claim outside the round is listed and not scored", "outside the round 1" in out, out[:1500])
        check("a rejected certificate carries the checker's reason", "rejected %s in 2: absence half" % M2WIDE in out, out[:1500])
        check("a corpus label contradicted by a certified result is listed",
              "certified shortest mate 2 where the corpus states 3" in out, out[:1500])
        check("an unreadable line is reported, not scored", "not scored: not JSON" in out, out[-1500:])
        check("pairing reports the discordant certified claims",
              any(l.split()[:4] == ["all", "4", "1", "0"] for l in out.splitlines()), out[-1200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lint():
    print("\nmeasurement lint")
    out = subprocess.run([sys.executable, str(HERE / "lint_measurement.py"), str(HERE / "absence.py"),
                          str(HERE / "certify.py")], capture_output=True, text=True)
    check("absence.py and certify.py pass the measurement lint", out.returncode == 0, out.stdout)


if __name__ == "__main__":
    import certificates
    certificates.checker()
    test_absence()
    test_references()
    test_minimality()
    test_certify_tool()
    test_lint()
    failed = [name for name, ok in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    for name in failed:
        print("  FAILED: %s" % name)
    sys.exit(1 if failed else 0)
