# Clocks, profiles and Huntsman: plan

Written 2026-09-17, before any engine ran at the clocks below except where
stated. It follows `studies/profile/`, which found MateHunter's recommended
profile ahead of stock Stockfish 19 at 5,000 ms and behind at 1,000 ms on mate in
9 to 11, and it asks two things:

1. **Where does the recommended profile overtake stock, and which MateHunter
   profile should a user pick at a given clock?**
2. **Does Huntsman 1's lead at equal nodes hold at equal time?** Huntsman was
   only ever measured under node budgets.

## Positions

| file | mate in | positions | sha256 |
|---|---|---:|---|
| `corpora/generated-deeper.epd` | 9 to 11 | 993 | `bd3a9da6c2556e16ec2c7be1d3e1fbbb4456d2ac877503064118c0754dcf921a` |
| `corpora/generated-deep-6to8-reachable.epd` | 6 to 8 | 1,171 | `5e06cec70d6b8373e40a2809edb8de39926cdf203d3774fa4bbeb7f6a8b47022` |

The second file is `corpora/generated-deep.epd` at mate in 6 to 8 without the 19
positions no game can reach (`studies/depth/RESULTS.md`), which Huntsman accepts
and the other engines refuse. It is rebuilt with `reachable_material` from
`bench/generate_corpus.py`, keeping line order.

## Measurement, fixed now

- **Arms:** `manifests/stockfish-19.json`, `manifests/matehunter-19.json`
  (recommended), `manifests/matehunter-19-kingdanger.json`,
  `manifests/huntsman-1.json`.
- **Runner:** `bench/submit.py --movetime`, one thread per search, 8 searches at a
  time, nothing else running, MateProver 0.2.0 verification at 1,000,000 nodes,
  on the machine of `studies/profile/` (Ryzen 9 7945HX, 16 cores, WSL2).
- **Clocks:** 500, 1,000, 2,000, 5,000 and 10,000 ms on mate in 9 to 11; 500,
  1,000, 2,000 and 5,000 ms on mate in 6 to 8.
- **Already run:** Stockfish 19 and both MateHunter profiles at 1,000 and 5,000
  ms on mate in 9 to 11 and at 1,000 ms on mate in 6 to 8, in
  `studies/profile/`. Those results are reused from the same cache, not re-run.
- **Pairs:** at every clock and range, recommended against Stockfish, king-danger
  against Stockfish, recommended against king-danger, Huntsman against
  recommended, and Huntsman against Stockfish; discordant pairs and two-sided
  sign test, as elsewhere.

## What would count

**Question 1.** On mate in 9 to 11:

- The **crossover** is the shortest clock at which the recommended profile is
  ahead of Stockfish 19 at p < 0.05, provided it is not behind at p < 0.05 at any
  longer clock tested. If no clock qualifies, there is no crossover in this range.
- **Profile advice** at a clock is whichever profile is ahead of the other at
  p < 0.05 there; where neither is, the advice is that they are level. The
  README gets advice only for clocks measured here.

**Question 2.** The primary comparison is Huntsman 1 against the recommended
profile at 5,000 ms on mate in 10 and 11 (304 positions), the primary set and
clock of `studies/profile/`. Either engine ahead at p < 0.05 settles which is
stronger there; otherwise they are level there. Every other Huntsman pair is
secondary.

Twenty-odd comparisons are reported, so an isolated p just under 0.05 among the
secondary ones is weak evidence, and the report will say so.
