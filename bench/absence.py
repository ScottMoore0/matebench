#!/usr/bin/env python3
"""Check minimality and absence certificates (docs/CERTIFICATES.md).

A finding certificate proves a mate within N and nothing more. Tracks 3 and 4
score two stronger claims - "the shortest mate is N" and "there is no mate within
k" - and this checker is what lets them score certificates instead of a prover's
word. It re-derives every legal move with python-chess and shares no code with
any engine. The mate half of a minimality certificate is checked by MateProver's
independent checker, `tools/verify_proof.py`, through bench/certificates.py.

    from absence import check
    verdict, reason = check("absence", fen4, 3, certificate)       # verified | rejected
    verdict, reason = check("minimality", fen4, 5, certificate)
"""
import sys

import chess

ABSENCE = "matebench-absence-1"
MINIMALITY = "matebench-minimality-1"


class Failure(Exception):
    pass


def _where(path):
    return " ".join(path) if path else "<root>"


def _move(board, uci, path, who):
    if not isinstance(uci, str):
        raise Failure("after %s: a %s move is missing or not a string" % (_where(path), who))
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise Failure("after %s: unparseable %s move %r" % (_where(path), who, uci))
    if move not in board.legal_moves:
        raise Failure("after %s: illegal %s move %s" % (_where(path), who, uci))
    return move


def check_absence_node(board, node, j, nodes, memo, path):
    """Raise Failure unless `node` shows the side to move cannot mate within `j` moves."""
    if not isinstance(node, dict):
        raise Failure("after %s: an absence node is not a JSON object" % _where(path))
    if "ref" in node:
        ref = node["ref"]
        if not isinstance(ref, str) or ref not in nodes:
            raise Failure("after %s: reference %r names no shared node" % (_where(path), ref))
        # A shared node is valid or not in THIS position with THIS budget; the
        # memo is keyed on both, never on the id alone.
        key = (board.fen(), j, ref)
        if key in memo:
            return
        check_absence_node(board, nodes[ref], j, nodes, memo, path)
        memo.add(key)
        return

    entries = node.get("m")
    if not isinstance(entries, list):
        raise Failure("after %s: an absence node has no move list" % _where(path))
    listed = sorted(e.get("a", "") if isinstance(e, dict) else "" for e in entries)
    legal = sorted(m.uci() for m in board.legal_moves)
    if listed != legal:
        missing = sorted(set(legal) - set(listed))
        extra = sorted(set(listed) - set(legal))
        detail = []
        if missing:
            detail.append("attacker moves not refuted %s" % missing)
        if extra:
            detail.append("lists illegal attacker moves %s" % extra)
        if not detail:
            detail.append("lists an attacker move more than once")
        raise Failure("after %s: %s" % (_where(path), "; ".join(detail)))

    for entry in entries:
        move = _move(board, entry.get("a"), path, "attacker")
        board.push(move)
        try:
            here = path + [move.uci()]
            if board.is_checkmate():
                raise Failure("after %s: this move mates, so a mate within the bound exists"
                              % _where(here))
            if "r" not in entry:
                if j == 1 or not any(True for _ in board.legal_moves):
                    continue
                raise Failure("after %s: %d attacker moves remain and the defender has moves, "
                              "so a defence must be given" % (_where(here), j - 1))
            if j < 2:
                raise Failure("after %s: a defence is given with no attacker move left" % _where(here))
            reply = _move(board, entry.get("r"), here, "defender")
            if "p" not in entry:
                raise Failure("after %s %s: a defence has no sub-proof" % (_where(here), reply.uci()))
            board.push(reply)
            try:
                check_absence_node(board, entry["p"], j - 1, nodes, memo, here + [reply.uci()])
            finally:
                board.pop()
        finally:
            board.pop()


def check_absence(fen4, k, cert):
    if not isinstance(cert, dict) or cert.get("format") != ABSENCE:
        raise Failure("not a %s certificate" % ABSENCE)
    if cert.get("k") != k:
        raise Failure("the certificate is for k = %r, the claim is k = %d" % (cert.get("k"), k))
    if not isinstance(k, int) or k < 1:
        raise Failure("k must be a positive integer")
    nodes = cert.get("nodes") or {}
    if not isinstance(nodes, dict):
        raise Failure("nodes must be a JSON object")
    board = chess.Board(fen4 + " 0 1")
    check_absence_node(board, cert.get("proof"), k, nodes, set(), [])


def check_minimality(fen4, n, cert):
    import certificates   # MateProver's checker, loaded from the configured checkout

    if not isinstance(cert, dict) or cert.get("format") != MINIMALITY:
        raise Failure("not a %s certificate" % MINIMALITY)
    if cert.get("n") != n:
        raise Failure("the certificate is for n = %r, the claim is n = %d" % (cert.get("n"), n))
    if not isinstance(n, int) or n < 1:
        raise Failure("n must be a positive integer")
    import json
    verdict, reason = certificates.verify(fen4, n, json.dumps(cert.get("mate")) if cert.get("mate") is not None
                                          else None, 1 << 62)
    if verdict != "verified":
        raise Failure("mate half: %s" % (reason or "missing"))
    shorter = cert.get("no_shorter")
    if n == 1:
        if shorter not in (None, {}):
            raise Failure("a mate in one needs no absence half, and one was given")
        return
    if shorter is None:
        raise Failure("no absence half: nothing shows there is no mate in %d" % (n - 1))
    try:
        check_absence(fen4, n - 1, shorter)
    except Failure as exc:
        raise Failure("absence half: %s" % exc)


def check(kind, fen4, n, cert):
    """('verified', '') or ('rejected', reason)."""
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 20000))
    try:
        chess.Board(fen4 + " 0 1")
        if kind == "absence":
            check_absence(fen4, n, cert)
        elif kind == "minimality":
            check_minimality(fen4, n, cert)
        else:
            raise Failure("unknown claim %r" % kind)
    except Failure as exc:
        return "rejected", str(exc)
    except ValueError as exc:
        return "rejected", "unusable position or move (%s)" % exc
    except RecursionError:
        return "rejected", "the certificate nests too deeply to check"
    except (KeyError, TypeError, AttributeError) as exc:
        return "rejected", "malformed certificate (%s: %s)" % (type(exc).__name__, exc)
    finally:
        sys.setrecursionlimit(limit)
    return "verified", ""
