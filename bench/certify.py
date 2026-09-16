#!/usr/bin/env python3
"""Score tracks 3 and 4 - minimality and absence - on certificates.

    python bench/matebench.py certify claims.jsonl --positions round.heldout.epd
    python bench/matebench.py certify claims.jsonl --against reference.jsonl --positions round.heldout.epd

A claims file is JSON Lines, one claim per line (docs/CERTIFICATES.md):

    {"fen": "...", "claim": "minimality", "n": 5, "certificate": {...}}
    {"fen": "...", "claim": "absence", "n": 4, "certificate": {...}}

Every certificate is checked by bench/absence.py, and the mate half of a
minimality certificate by MateProver's independent checker. Nothing an entrant
reports counts without a certificate that checks: a claim with none is
uncertified, and a certificate that fails is rejected with the checker's reason.

With --positions, the round's positions are the denominator: a position with no
verified claim is not solved, and a claim on a position outside the round is
listed and not scored. For a minimality claim, the corpus's stated mate length
is compared with the certified one, and every disagreement is listed: a
certified minimality result that contradicts the corpus label means the label
is wrong.

With --against, a second entrant's claims are paired with the first's per band,
per claim type, as discordant pairs with a two-sided sign test.
"""
import argparse
import json
import re
import sys
from math import comb
from pathlib import Path

import absence

BANDS = [(1, 7), (8, 12), (13, 17), (18, 21), (22, 25), (26, 30), (31, 999)]
BM = re.compile(r"\bbm\s+#(\d+)")


def band_of(n):
    for lo, hi in BANDS:
        if lo <= n <= hi:
            return "d%d-%s" % (lo, hi if hi < 999 else "+")
    return "?"


def sign_p(w, l):
    n = w + l
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0


def fen4(text):
    return " ".join(text.split()[:4])


# A MateProver result line from --minimality-proof or --absence-proof, as it prints it.
MP_CLAIM = re.compile(r"; (?:dm (\d+); minimality ok|absence (\d+); ok);.*; (minproof|absproof) (\{.*\});\s*$")
# The same modes answering without a certificate: mate-exists, inconclusive, too-large, or no mate proved.
MP_ANSWER = re.compile(r"; ((?:absence \d+; [a-z-]+)|(?:minimality(?: [a-z-]+|; [^;]+)))")


def from_mateprover(line):
    """A claim read from a MateProver certificate line, or None."""
    m = MP_CLAIM.search(line)
    if not m:
        return None
    try:
        cert = json.loads(m.group(4))
    except json.JSONDecodeError:
        return None
    return {"fen": fen4(line.split(";", 1)[0]), "claim": "minimality" if m.group(3) == "minproof" else "absence",
            "n": int(m.group(1) or m.group(2)), "certificate": cert}


def load_claims(path, max_bytes):
    """[(line number, claim dict or None, problem)]"""
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            if len(line.encode("utf-8")) > max_bytes:
                out.append((number, None, "line is over the %d-byte limit" % max_bytes))
                continue
            try:
                claim = json.loads(line)
            except json.JSONDecodeError as exc:
                claim = from_mateprover(line)
                if claim is None:
                    answer = MP_ANSWER.search(line)
                    if answer:
                        out.append((number, None, "MateProver answered without a certificate: %s"
                                    % answer.group(1).strip()))
                    else:
                        out.append((number, None, "not JSON, and not a MateProver certificate line (%s)" % exc))
                    continue
            if (not isinstance(claim, dict) or claim.get("claim") not in ("minimality", "absence")
                    or not isinstance(claim.get("n"), int) or not isinstance(claim.get("fen"), str)):
                out.append((number, None, "needs fen, claim (minimality or absence) and an integer n"))
                continue
            out.append((number, claim, ""))
    return out


def score(path, max_bytes):
    """{(claim type, fen4): {"n": n, "verdict": ..., "reason": ...}} plus a list of unusable lines."""
    results, unusable = {}, []
    for number, claim, problem in load_claims(path, max_bytes):
        if claim is None:
            unusable.append((number, problem))
            continue
        fen = fen4(claim["fen"])
        cert = claim.get("certificate")
        if cert is None:
            verdict, reason = "uncertified", "no certificate"
        else:
            verdict, reason = absence.check(claim["claim"], fen, claim["n"], cert)
        key = (claim["claim"], fen)
        if key in results:
            unusable.append((number, "a second %s claim for %s; the first is kept" % key))
            continue
        results[key] = {"n": claim["n"], "verdict": verdict, "reason": reason}
    return results, unusable


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("claims")
    ap.add_argument("--against", default="", help="a second entrant's claims file, paired per band")
    ap.add_argument("--positions", default="", help="the round's positions (EPD with bm #N)")
    ap.add_argument("--max-certificate-mb", type=float, default=512.0)
    a = ap.parse_args(argv)
    max_bytes = int(a.max_certificate_mb * 1024 * 1024)

    corpus = {}
    if a.positions:
        for line in Path(a.positions).read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = BM.search(line)
            if m and not line.startswith("%"):
                corpus[fen4(line.split(" bm ")[0])] = int(m.group(1))

    entrants = [(a.claims, *score(a.claims, max_bytes))]
    if a.against:
        entrants.append((a.against, *score(a.against, max_bytes)))

    for name, results, unusable in entrants:
        print("\n  %s" % name)
        for kind in ("minimality", "absence"):
            rows = {fen: r for (k, fen), r in results.items() if k == kind}
            if not rows and not corpus:
                continue
            counts = {"verified": 0, "rejected": 0, "uncertified": 0}
            for r in rows.values():
                counts[r["verdict"]] += 1
            outside = [fen for fen in rows if corpus and fen not in corpus]
            print("    %-10s claims %5d, verified %5d, rejected %5d, uncertified %5d%s"
                  % (kind, len(rows), counts["verified"], counts["rejected"], counts["uncertified"],
                     (", outside the round %d (not scored)" % len(outside)) if outside else ""))
            for fen, r in list((f, r) for f, r in rows.items() if r["verdict"] == "rejected")[:5]:
                print("      rejected %s in %d: %s" % (fen, r["n"], r["reason"]))
            if kind == "minimality" and corpus:
                wrong = [(fen, r["n"], corpus[fen]) for fen, r in rows.items()
                         if r["verdict"] == "verified" and fen in corpus and corpus[fen] != r["n"]]
                for fen, got, stated in wrong[:10]:
                    print("      certified shortest mate %d where the corpus states %d: %s" % (got, stated, fen))
                if wrong:
                    print("      %d corpus label(s) contradicted by a certified result" % len(wrong))
        for number, problem in unusable[:10]:
            print("    line %d not scored: %s" % (number, problem))

    if corpus:
        for kind in ("minimality", "absence"):
            print("\n  %s, verified per band of the round's stated mate length" % kind)
            print("  %-9s %5s " % ("band", "n") + " ".join("%12s" % Path(n).stem[:12] for n, _, _ in entrants))
            for lo, hi in BANDS:
                group = {fen for fen, d in corpus.items() if lo <= d <= hi}
                if not group:
                    continue
                cells = []
                for _, results, _ in entrants:
                    cells.append(sum(1 for fen in group if results.get((kind, fen), {}).get("verdict") == "verified"))
                print("  %-9s %5d " % (band_of(lo), len(group)) + " ".join("%12d" % c for c in cells))

    if len(entrants) == 2:
        (na, ra, _), (nb, rb, _) = entrants
        for kind in ("minimality", "absence"):
            va = {fen for (k, fen), r in ra.items() if k == kind and r["verdict"] == "verified"}
            vb = {fen for (k, fen), r in rb.items() if k == kind and r["verdict"] == "verified"}
            if not va and not vb:
                continue
            universe = set(corpus) if corpus else (va | vb)
            print("\n  %s: %s against %s, paired on certified claims" % (kind, Path(na).stem, Path(nb).stem))
            print("  %-9s %5s %8s %8s %8s" % ("band", "n", "a only", "b only", "p"))
            W = L = 0
            for lo, hi in BANDS:
                depth = corpus if corpus else {fen: (ra.get((kind, fen)) or rb.get((kind, fen)))["n"] for fen in universe}
                group = {fen for fen in universe if lo <= depth[fen] <= hi}
                if not group:
                    continue
                w, l = len((va - vb) & group), len((vb - va) & group)
                W, L = W + w, L + l
                print("  %-9s %5d %8d %8d %8.4f" % (band_of(lo), len(group), w, l, sign_p(w, l)))
            print("  %-9s %5d %8d %8d %8.4f" % ("all", len(universe), W, L, sign_p(W, L)))
    print("\n  Only certified claims score. The discordant pairs per band are the result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
