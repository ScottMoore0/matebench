#!/usr/bin/env python3
"""Submitter certificates: proof trees an entrant supplies for its own claims.

Without them, a claim counts only if MateProver re-proves it within the
verification budget, and one it cannot re-prove is reported as unconfirmed. That
caps every entrant at MateProver's reach: an engine that finds mates MateProver
cannot prove gets no credit for them, however right it is.

A certificate removes the cap. It is a complete proof tree in MateProver's
certificate format, version 1 (docs/PROOF_FORMAT.md in the MateProver
repository, written so that anyone can produce one without reading MateProver).
Whoever produced it, it is checked by `tools/verify_proof.py` from the configured
MateProver checkout: a separate program that re-derives every legal move with
python-chess and shares no code with any engine. It accepts a certificate only if

  * the attacker's move at every node is legal;
  * every leaf marked mate is checkmate;
  * every defender node lists exactly the legal replies, none missing, none
    invented, none twice;
  * the certificate's depth equals the claimed mate distance.

The checker starts from the corpus position, never from anything the submitter
sends, so a valid certificate for some other position cannot pass. What the
submitter's prover is, and whether it can be trusted, does not matter: a
certificate either checks or it does not.

A certificate proves a mate within its depth. It does not prove that no shorter
mate exists, so it scores on the finding track and never on minimality.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import chess

import config

# `proof <json>` in MateProver's wire format, where the JSON runs to the end of
# the line and may be followed by the line's closing `;`.
PROOF_TOKEN = re.compile(r"\bproof\s+(\{.*\})\s*;?\s*$")

_checker = None


def checker():
    """The independent checker, loaded from the configured MateProver checkout.

    Loaded from the file rather than copied into this repository, so the checker
    that ran is the one the log names, by path and sha256.
    """
    global _checker
    if _checker is None:
        path = Path(config.MATEPROVER_REPO) / "tools" / "verify_proof.py"
        if not path.exists():
            raise SystemExit(
                "certificate checker not found: %s\n"
                "  set MATEBENCH_MATEPROVER_REPO to a MateProver checkout (v0.2.0):\n"
                "  git clone --branch v0.2.0 https://github.com/ScottMoore0/mateprover" % path)
        spec = importlib.util.spec_from_file_location("matebench_verify_proof", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.checker_path = str(path)
        module.checker_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        _checker = module
    return _checker


def extract(text):
    """The certificate JSON in a prover's output, or None.

    Accepts MateProver's result line (`...; proof <json>;`) or a line that is a
    JSON object on its own. The last such line wins.
    """
    if not text:
        return None
    for line in reversed(text.splitlines()):
        s = line.strip()
        m = PROOF_TOKEN.search(s)
        if m:
            return m.group(1)
        if s.startswith("{") and s.endswith("}"):
            return s
    return None


def verify(fen4, claimed, raw, max_bytes):
    """Check a certificate for mate in `claimed` from `fen4`.

    Returns (verdict, reason), the verdict one of
      absent    no certificate was supplied
      verified  the certificate checks, at exactly the claimed depth
      rejected  it does not; `reason` says why
    """
    if raw is None:
        return "absent", ""
    size = len(raw.encode("utf-8"))
    if size > max_bytes:
        return "rejected", "certificate is %d bytes, over the %d-byte limit" % (size, max_bytes)
    try:
        node = json.loads(raw)
    except json.JSONDecodeError as exc:
        return "rejected", "not JSON (%s)" % exc
    if not isinstance(node, dict):
        return "rejected", "the certificate root is not a JSON object"
    try:
        board = chess.Board(fen4 + " 0 1")
    except ValueError as exc:
        return "rejected", "unusable position (%s)" % exc

    check = checker()
    # A certificate nests two frames per move; the deepest corpus mates are about
    # 130 moves. The limit is raised for the check and restored afterwards.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 20000))
    try:
        proved = check.verify_node(board, node, [], "mate")
    except check.Failure as exc:
        return "rejected", str(exc)
    except RecursionError:
        return "rejected", "the certificate nests too deeply to check"
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        # A malformed node, such as a reply without "p" or "d" that is not a
        # list, is a certificate that does not check, not a harness failure.
        return "rejected", "malformed certificate (%s: %s)" % (type(exc).__name__, exc)
    finally:
        sys.setrecursionlimit(limit)
    if proved != claimed:
        return "rejected", "the certificate proves mate in %d, the claim is mate in %d" % (proved, claimed)
    return "verified", ""
