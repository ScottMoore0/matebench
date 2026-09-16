# Certificates for minimality and absence

A finding claim - "the side to move forces mate within N" - is certified by a
proof tree in MateProver's certificate format, version 1 (`docs/PROOF_FORMAT.md`
in the MateProver repository), and `bench/certificates.py` checks it.

That format cannot certify the claims tracks 3 and 4 score. "The shortest mate
is N" and "there is no mate within k" are claims about every line, not about one
winning strategy, and MateProver's certificate format says so itself: it does not
claim minimality. Until now those two tracks scored a prover's word. This
document specifies certificates for both, precisely enough to produce one without
reading any engine, and `bench/absence.py` checks them.

## Absence: `matebench-absence-1`

**Claim.** The side to move (the attacker) cannot force checkmate within `k`
of its own moves, `k >= 1`, whatever it plays, against the defender's best
replies.

```json
{"format": "matebench-absence-1", "k": 3, "proof": <AbsenceNode>, "nodes": {<id>: <AbsenceNode>, ...}}
```

### Grammar

```
AbsenceNode := { "m": [ Refutation, ... ] }
             | { "ref": "<id>" }
Refutation  := { "a": Move }                                   // a leaf
             | { "a": Move, "r": Move, "p": AbsenceNode }      // a defence
Move        := UCI coordinate string, e.g. "e2e4", "e7e8q"
```

The root node is in the claim's position with the attacker to move and `j = k`
attacker moves left. `nodes` is optional; it holds shared sub-proofs that
`{"ref": id}` points to.

### What a checker must verify

At an `AbsenceNode` with `j` attacker moves left:

1. The multiset of `"a"` values is **exactly** the attacker's legal moves: none
   missing, none illegal, none twice. A position with no legal attacker move
   has `"m": []`, and the attacker cannot mate from it.
2. For each refutation, after `"a"`:
   - the position is **not checkmate** (if it is, a mate within the bound
     exists and the certificate is false);
   - a **leaf** (`"a"` only) is valid when `j == 1`, so no attacker move is left
     to mate with, or when the defender has no legal move, so the move was
     stalemate and the game is over without mate;
   - a **defence** (`"r"` and `"p"`) is valid when `j >= 2`, `"r"` is a legal
     defender move, and `"p"` is a valid `AbsenceNode` after `"r"` with `j - 1`
     attacker moves left.
3. A `{"ref": id}` node is checked as the node `nodes[id]`, **in the position
   and with the `j` where the reference appears**. The same shared node may be
   valid in one position and not another; every use is checked against its own
   position. A checker may remember a use it has already checked, keyed by the
   position, `j` and `id`.

A leaf where the defender still has moves and `j >= 2` is rejected: the
attacker has moves left, so the certificate has to say which defence stops them.
A defence given when `j == 1` is rejected too, so that every certificate has one
reading.

Draws by repetition, the fifty-move rule and insufficient material play no part,
as in MateProver's own format: a stipulation "within k moves" is decided by the
moves alone.

### Size

Absence certificates list every attacker move at every attacker node, so they
are larger than mate certificates of the same depth. Shared nodes are what keep
them tractable: a search that reaches the same position by different move
orders can prove it once and refer to it.

## Minimality: `matebench-minimality-1`

**Claim.** The side to move forces mate in `N`, and in no fewer.

```json
{"format": "matebench-minimality-1", "n": 5, "mate": <MateProver v1 certificate>, "no_shorter": <absence certificate>}
```

- `mate` is a certificate in MateProver's format, version 1, whose depth is
  exactly `n`. It is checked by MateProver's independent checker,
  `tools/verify_proof.py`.
- `no_shorter` is a `matebench-absence-1` certificate for the same position with
  `k = n - 1`. It is omitted, or `null`, when `n == 1`: nothing is shorter than a
  mate in one.

Both halves are checked from the claim's position. Neither can be satisfied by a
proof about another position.

## Claims files

`bench/certify.py` scores a claims file in JSON Lines, one claim per line:

```json
{"fen": "<four FEN fields>", "claim": "minimality", "n": 5, "certificate": {...}}
{"fen": "<four FEN fields>", "claim": "absence", "n": 4, "certificate": {...}}
```

A line without a certificate is recorded as uncertified, never as verified.
With `--positions`, every position of the round is accounted for: a position
with no claim counts as not solved, and a claim on a position outside the round
is reported and not scored.

## Who emits them

`bench/test_certify.py` builds both kinds by exhaustive search for small
positions, to test the checker.

MateProver emits both, from the version after 0.2.0: `--absence-proof` and
`--minimality-proof` print a result line ending in an `absproof` or `minproof`
certificate, and `bench/certify.py` reads those lines directly as well as JSON
Lines. On 290 generated positions, mate in 1 to 4, all 290 minimality
certificates and all 190 absence certificates it emitted verified here, and it
refused an absence certificate at the shortest mate on all 290. MateProver 0.2.0
does not emit them, so the minimality figures in the reference results, which
were measured with 0.2.0, remain its claims, not certified results.

These certificates grow exponentially with the bound: every attacker move is
answered at every level. MateProver's minimality certificate for a mate in 4 on a
busy board has a few thousand shared nodes. Certified minimality far deeper than
that needs a more compact proof than this format.

A prover that emits these certificates is scored on tracks 3 and 4 without anyone
having to trust it.
