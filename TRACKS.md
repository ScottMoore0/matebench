# Tracks

Every track states what is measured, how it is budgeted, and what counts as a
result. Two rules apply to all of them.

**Budgets.** Within one engine family (two Stockfish forks, two configurations
of the same binary) the budget is a **node limit**: deterministic, reproducible,
and immune to machine load. Across families (a DFPN prover against an
alpha-beta fork) it is **wall-clock**, because a node is not the same unit of
work in two different searches and a node budget would hand the advantage to
whichever engine defines a node more cheaply. Wall-clock runs happen on an idle
machine, and the load average is recorded.

**Pairing.** Every arm sees every position. A run reports, per depth band, the
count per arm, the positions only one arm got (the discordant pairs) and a
two-sided sign test on those. **The discordant pairs are the result; the totals
are context.** Bands are reported separately and never only pooled.

---

## 1. Finding - a mate within N

The submission is asked `go mate N` for a position whose shortest mate is N.
It reports a mate distance `dm`. The claim is accepted only if:

- `0 < dm <= N` - a *negative* UCI mate score means the side to move is being
  mated, and is not a solve (taking the absolute value of a mate score voided
  an entire workstream once);
- it is verified, in one of two ways:
  - the submission supplies a **certificate** for it, a proof tree in
    MateProver's certificate format, and MateProver's independent checker
    (`tools/verify_proof.py`, sharing no code with any engine) accepts it at
    exactly depth `dm`; or
  - MateProver `--direct-depth -z dm` re-proves it within the verification
    budget. The reference results used MateProver v0.2.0, or v0.1.0 before
    2026-09-13, which searches identically; the README says where to get it and
    why the build is recorded.

A claim with no certificate, or with one the checker rejects, is re-proved.
Unverified-within-budget is reported as **unconfirmed**, not as false. The
verification budget is 1,000,000 nodes: verification cost is bimodal (median
90K, maximum 20M), a ceiling is spent only on failures, and 1M verified as many
claims as 4M for a quarter of the wasted work. Raise it if you can show it
changes the count. The budget binds only claims without a certificate, so a
submission whose mates are beyond it can still have them verified by supplying
certificates (SUBMISSION.md).

Scored per band; bands are d8–12, d13–17, d18–21, d22–25, d26–30, d31+.

## 2. Speed - time to a verified find

On the positions **both** arms solved (a ratio including a timeout is a number
against a cap), the paired time per position. Reported as: which arm was faster
on how many, sign test, median and mean ratio. Process startup is measured and
subtracted where it is not negligible; at ~5 ms it usually is.

## 3. Minimality - the shortest mate, certified

The submission must state the shortest mate, and the certificate must prove
that no shorter one exists. Alpha-beta engines cannot enter: an alpha-beta "no
mate in N−1" means "not found within budget", not "does not exist". A
`--direct-depth`-style answer is a finding result and scores on track 1, never
here.

The two are **never merged**. A prover's output line carries which claim it is
making, and the harness keeps the columns apart.

## 4. Absence - no mate within N, certified

The engine is given a position and a bound and must prove there is no mate
within it. Scored on certified absences within budget. This is the track that
distinguishes a prover from a finder, and it is where 99.3% of a prover's work
goes on the minimality track.

## 5. Other goals

Stalemate, selfmate, selfstalemate, helpmate, helpstalemate - each a distinct
stipulation (a checkmate *fails* a stalemate goal). Corpora: public composed
problems where licensing allows, otherwise generated. Scored as track 1 or 3
according to whether the entrant proves the shortest solution.

## 6. Variant rules

x-check (win on the Nth check), x-capture (win on the Nth capture), x-escape
(lose when your king's escape count reaches N), composable with every goal and
asymmetric per side. **No corpus and no second entrant exist for these yet.**
The reference prover reaches the initial position of x-capture chess in 5, 9
and ≥15 plies for x = 1, 2, 3 - each a certified minimum, or a certified lower
bound in the last case.

---

## What is deliberately not a track

**Node rate.** Nodes per second is not comparable across engines and, within
one, converts to coverage as `log_r(S)` with r ≈ 3.7 per ply - a verified 1.22×
speedup produced +0 solves per hundred. A track that rewarded it would reward
the wrong thing.

**Unsound finders scored on their claims.** MateProver's own `--beam-defender`
claimed more positions than the exhaustive search at every depth and verified
fewer; 14-28% of its claims were false shorter mates. Counting claims would have
ranked it first. See the reference results.

**Unverified solve counts.** See track 1. The number every mate-solver
benchmark has historically reported is the number this one refuses to.
