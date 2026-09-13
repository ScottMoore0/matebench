# Reference results

Every number below was produced by a script in `bench/` and the raw log is in
this directory, dated. Where a result is *not established* it says so. Read the
configuration column: two of these engines are measured at settings that are
not their defaults, because their defaults switch the mate solver off.

## Engines and configurations

**What a third party can obtain.** MateProver is public and pinned below.
Chest, Matefish, Huntsman and Stockfish are distributed by their own authors,
and the table below says where. **MateHunter is not distributed**: it is a private
Stockfish fork, so every row naming it is recorded for the protocol's sake and
cannot be reproduced by anyone else. The tracks and budgets do not depend on
it.

| engine | base | manifest used | notes |
|---|---|---|---|
| MateProver 0.1.0 | own DFPN | defaults; `--direct-depth` on finding tracks, `--iterative-depth` on minimality | emits certificates; MIT, https://github.com/ScottMoore0/mateprover at tag v0.1.0 |
| MateHunter 18 | Stockfish 18 fork | `MateEval=true`, `MateMode=false` | shipped default as of 2026-09-02; `MateMode=true` costs 21/234 at d26+ |
| MateHunter 19 | Stockfish 19 fork | `MateEval=true`, `MateMode=false`, every other mate option set off explicitly | port of the 18 fork; with every mate option off it is node-for-node identical to stock (bench 2,497,913). Recommended profile from 2026-09-13 adds `MateEvalNull=true`; see "Recommended profile" |
| Stockfish 19 | own (NNUE) | defaults with `Threads=1`, `Hash=256` | https://stockfishchess.org; built from the release source with the fork's compiler and flags |
| Huntsman 1 | Stockfish fork | `MateSearch=true` (its default) | over-claims; echoes toward the bound; by joergoster, https://github.com/joergoster/Stockfish-old/releases/tag/h1 (the binary used self-identifies as `The Huntsman 1`) |
| Matefish 170826 | Stockfish + PNS | `ProofNumberSearch=true`, `PNS Hash=4096` | **both default off/small**; at defaults it abandons a d14 search in 0.2 s |
| Chest 3.19 | own | `WinChest.exe`, job on stdin, 2048 MB, `UseDatabase=false` | 1999-era; endgame databases off (they reach ~1% of proof nodes here). **Not `ChestUCI.exe`**: that is the GUI/UCI wrapper, and fed a job it spins with no output, which a harness scores as a timeout |

## Finding, verified - MateProver vs Matefish (`vs_matefish_2026-09-12.log`)

60 positions, d8–16, 10 s each, single-threaded. Claims verified by MateProver
`--direct-depth`. Re-measured 2026-09-12; the minimality row of the previous
run was not measuring minimality, see the retraction below.

| band | n | MateProver | Matefish claimed | Matefish verified |
|---|---|---|---|---|
| d8 | 12 | 10 | 10 | 10 |
| d10 | 12 | 10 | 11 | 10 |
| d12 | 12 | 10 | 10 | 9 |
| d14 | 12 | 7 | 8 | 5 |
| d16 | 12 | 8 | 7 | 7 |
| **total** | **60** | **45** | 46 | **41** |

Paired: Matefish +0/−4, 4 discordant, **p = 0.125 - parity, not established
either way**.

**Minimality: MateProver 14/60**, by band 7/3/3/1/0 across d8–d16; Matefish n/a
(echoes the bound). The minimality lane runs `--no-portfolio`: a restricted
lane searches the requested depth directly and cannot establish a shortest
mate, so leaving the portfolio on spends the budget on lanes that are
structurally unable to answer.

Speed on the 41 both solved: MateProver faster on 36, p < 0.0001, median 3.84×.
**This row is not comparable with the pre-2026-09-12 one.** The script that
produced the earlier speed figure is not in the tree and its method cannot be
recovered, and this run was taken under WSL rather than natively. The counts
above are proof counts and are platform-independent; these two numbers are wall
clock and are not.

## Finding - MateHunter vs Huntsman (`h2h_chestuci_*.log`, `h2h_deep_*.log`)

ChestUCI corpus (neither engine tuned on it), 10M nodes, 1 thread, paired.

| band | n | MateHunter | Huntsman | MH only | HS only | p |
|---|---|---|---|---|---|---|
| d14–17 | 196 | 157 | 147 | 24 | 14 | 0.143 |
| **d18–21** | 76 | 56 | 42 | 16 | 2 | **0.001** |
| d22–25 | 30 | 14 | 14 | 6 | 6 | 1.000 |
| d26–30 (all 65) | 65 | 19 | 28 | 2 | 11 | 0.022 |
| d31+ (all 155) | 155 | 24 | 37 | 6 | 19 | 0.015 |

Two opposite, established effects. **With `MateMode=false`** the deep rows
become 64 vs 65 (+17/−18, p = 1.0) and the d18–21 lead holds (+15/−2, p = 0.002);
MateHunter against itself on the 234 deep positions: +28/−7, p = 0.0005. With
`MateEval=false` it loses everywhere (154 vs 231 on the 400-sample).

## Finding - MateHunter 19 vs stock Stockfish 19 (`vs_stockfish_2026-09-12.log`)

ChestUCI, all 953 positions at d14+ (neither engine tuned on it), 10M nodes,
1 thread, paired. MateHunter is a Stockfish 19 derivative on the same source,
network, compiler and flags. With every mate option off it is node-for-node
identical to stock, and here 343 = 343 with zero discordant positions: the control
holds over the whole corpus, not just bench.

| band | n | MateHunter 19 | Stockfish 19 | MH only | SF only | p |
|---|---|---|---|---|---|---|
| d14–17 | 449 | 349 | 220 | 148 | 19 | <0.0001 |
| d18–21 | 186 | 123 | 69 | 61 | 7 | <0.0001 |
| d22–25 | 84 | 53 | 26 | 31 | 4 | <0.0001 |
| d26–30 | 65 | 26 | 11 | 18 | 3 | 0.0015 |
| d31+ | 169 | 35 | 17 | 21 | 3 | 0.0003 |
| **total** | **953** | **586** | **343** | **279** | **36** | **<0.0001** |

### Why MateEval works: mostly the absence of an evaluation

| arm (same 953 positions, 10M nodes) | solved |
|---|---|
| stock Stockfish 19 | 343 |
| NNUE with razoring, futility and null-move pruning off | 330 |
| king danger in the main search only | 343 |
| king danger in quiescence only | 317 |
| **constant evaluation, 0 everywhere** | **590** |
| full king-danger evaluator (shipped) | 586 |
| **escape squares only** | **635** |

- **A constant evaluation does as well as the full evaluator:** 590 against 586,
  +68/−64 paired, p = 0.79. Nearly all of the gain over stock comes from *not*
  using NNUE's game-outcome evaluation, not from knowledge of king danger. The
  earlier account - MateEval works because it ignores material while measuring
  king danger - is half right, and the half that matters is ignoring material.
- **It is not the pruning MateMode gates.** Switching razoring, futility and
  null-move pruning off under NNUE gains nothing (330 against 343, +73/−86,
  p = 0.34), so a flat evaluation is not merely disabling those three.
- **Escape squares beat the full evaluator but not a constant.** At d14+
  escape-squares-only beat both (+89/−40 over the evaluator; +88/−43 over the
  constant, p = 0.0001), but the second did NOT replicate at d10–13 (below), so
  it is not a finding.
- **Neither consumer alone reproduces it.** Main-search-only is level with stock
  and quiescence-only is slightly worse (+65/−91, p = 0.045). These two arms put
  two evaluation scales in one search - bench at depth 13 goes from 2.50M nodes
  for stock to 60.0M for main-search-only - so what they show is that the
  evaluation must be consistent across the search, not which consumer carries
  the effect.
- Node-budgeted, so speed plays no part in these counts. How speed changes them
  is measured under a clock below.

### Replication, out of sample (`vs_stockfish_d10-13_2026-09-13.log`)

ChestUCI d10–13, 1,524 positions the run above did not use, same budget and arms.

| arm | solved | paired |
|---|---|---|
| stock Stockfish 19 | 757 | - |
| NNUE with razoring, futility and null-move pruning off | 730 | +119/−146 vs stock, p = 0.11 |
| full king-danger evaluator (shipped) | 1,176 | +478/−59 vs stock |
| escape squares only | 1,210 | +116/−82 vs full evaluator, p = 0.019 |
| **constant evaluation** | **1,225** | **+520/−52 vs stock; +145/−96 vs full evaluator, p = 0.002** |

What replicates, and is therefore the finding:

1. **MateHunter's gain over stock Stockfish 19 is real and large** at both depth
   ranges: +279/−36 at d14+, +478/−59 at d10–13.
2. **It comes from replacing NNUE's evaluation with a flat one.** A constant
   evaluation matches the full evaluator at d14+ and beats it at d10–13. The
   king-danger terms the fork was built around add nothing, and at shallower depth
   they cost positions.
3. **It is not razoring, futility or null-move pruning.** Turning those off under
   NNUE gains nothing at either depth range.
4. Escape squares alone are at least as good as the full evaluator; that they beat
   a constant did not replicate.

### Under a clock (`vs_stockfish_t5000_*_2026-09-13.log`)

The same positions at 5 seconds a position instead of 10M nodes, one thread, 12
positions at a time on an otherwise idle machine.

| arm | d14+, 953 | d10–13, 1,524 | nps (d14+) |
|---|---|---|---|
| stock Stockfish 19 | 324 | 715 | 1.44M |
| full king-danger evaluator (shipped) | 592 | 1,195 | 2.57M |
| **constant evaluation** | **606** | **1,244** | 2.80M |

- **The constant evaluation is still at least as good as the full evaluator:**
  +72/−58 at d14+ (p = 0.25; the d14–17 band alone +37/−20, p = 0.033) and
  +136/−87 at d10–13 (p = 0.0013).
- Against stock it is +308/−26 at d14+ and +565/−36 at d10–13.
- The clock widens the gap over **stock** (both mate-oriented arms search close
  to twice stock's nodes per second), but barely changes the gap between the two
  flat evaluations, which differ in speed by about 9%.

### Which consumer carries it (`vs_stockfish_consumers_*_2026-09-13.log`, `vs_stockfish_correval_d14+_2026-09-13.log`)

`MateEvalOff` switches off one consumer of the static evaluation per bit. Every
switch was run at 10M nodes on d14+ twice: under the constant evaluation
(against the constant evaluation) and under NNUE (against the all-off control).
The switches that moved anything were re-run on d10–13.

| switched off | constant, d14+ | constant, d10–13 | NNUE, d14+ | NNUE, d10–13 |
|---|---|---|---|---|
| nothing | 590 | 1,225 | 343 | 757 |
| correction history in the static evaluation only | **169** (+5/−426) | **732** (+45/−538) | 293 (+22/−72) | 710 (+60/−107) |
| correction history everywhere | 159 (+8/−439) | 677 (+48/−596) | 300 (+30/−73) | 689 (+66/−134) |
| quiet-move futility pruning | 556 (+47/−81, p = 0.003) | 1,181 (+77/−121, p = 0.002) | 288 (+28/−83) | 673 (+66/−150) |
| improving flags | 542 (+42/−90) | 1,194 (+88/−119, p = 0.037) | 314 (+39/−68, p = 0.007) | 737 (+71/−91, p = 0.14) |
| aspiration windows | 567 (+64/−87, p = 0.07) | - | 309 (+43/−77, p = 0.002) | 719 (+76/−114, p = 0.007) |
| each of the other seven | 570–587, none p < 0.05 | - | 323–334 | - |

The other seven are eval-difference move ordering, ProbCut, capture futility,
move-count pruning, the LMR eval term, quiescence futility and history bonus
scaling.

What replicates, and is therefore the finding:

1. **The "constant evaluation" is not flat.** With the evaluation fixed at 0,
   what the search sees as the static evaluation is the correction-history term
   alone: the adjustment Stockfish learns during the search from how search
   results differ from the static evaluation, keyed by pawn structure, minor
   pieces, non-pawn material and the preceding moves. Take that term out of the
   static evaluation and the arm falls from 590 to 169 at d14+ and from 1,225 to
   732 at d10–13 - below stock both times. **A genuinely flat evaluation is
   worse than NNUE.**
2. **So MateHunter's gain comes from replacing NNUE's evaluation with one learned
   inside the current search.** Removing correction history from the evaluation
   costs nearly as much as removing it everywhere, so its other uses (margins
   and reductions) are not what matters.
3. **No consumer is misled by NNUE on its own.** Switching any single one off
   under NNUE recovers none of the gain; every NNUE arm is at or below the
   control.
4. Under the learned evaluation, quiet-move futility pruning and the improving
   flags both help, at both depth ranges.

The interpretation - that inside a forced-mate search the search's own results
are a better guide than a game-outcome network - is a reading of these numbers,
not a separate measurement.

### Recommended profile

**`MateEval=true`, `MateEvalNull=true`, `MateMode=false`**, replacing the full
king-danger evaluator. It matches the evaluator at d14+ and beats it at d10–13,
under a node budget (590 vs 586; 1,225 vs 1,176, p = 0.002) and under a clock
(606 vs 592; 1,244 vs 1,195, p = 0.0013), and what it does can now be stated
exactly. The engine's defaults are unchanged; the harness sets every toggle
explicitly and so should anyone reproducing these numbers.

## All six goals - MateProver vs Chest 3.19

From `mateprover/docs/RESULTS.md`, whole corpora, both proving the shortest
solution, 10 s a position:

| goal | corpus | Chest | MateProver |
|---|---|---|---|
| mate-in-8 | 200 | 146 | 167 |
| mate-in-10 | 60 | 20 | 52 |
| stalemate | 792 | 725 | 761 |
| helpmate | 546 | 491 | 513 |
| helpstalemate | 431 | 308 | 363 |
| selfmate | 903 | 407 | **643** (re-measured 2026-09-03 under the final protocol; `selfmate_final_2026-09-03.log`; 388 both solved, 3.02x total / 3.51x median) |
| selfstalemate | 76 | 49 | 52 |

## Budgets and gates

- **Verification ceiling** (`verify_budget_2026-08-30.log`): cost bimodal,
  median 90,362 nodes, max 20.4M; 1M verifies as many claims as 4M; derivation
  controlled 6/6 at both ends of the cost range.
- **Ninth portfolio lane** (`lane9_*.log`): at a real lane budget, 1 rescued
  position of 45 at both d10–14 and d16–20. The restriction family is exhausted.
- **Lane-0 weight** (`lane0_sweep_2026-08-30.log`): flat 30–90%.
- **Defender-reply pruning** (`beam_experiment_2026-09-04.log`, `bench/beam_experiment.py`):
  MateProver `--beam-defender K` (keep the first K replies in the engine's own
  ordering, unsound, every claim re-proved at 50M nodes) against plain
  `--direct-depth` at 20M, 100 ChestUCI positions, four bands. **Zero verified
  finds the exhaustive search missed, at K = 2, 3 or 5**; plain-only 13 / 8 / 6,
  p = 0.0002 / 0.0078 / 0.031; false shorter claims 28% / 19% / 14%. The omitted
  reply is the refutation of a shorter line, so the beam proves a false dm and
  stops. Strictly dominated. The one lever that attacked the exponent, closed.
- **Generate-and-verify** (`genverify_*.log`): **+0** against a correctly
  configured baseline. The earlier "+24" was the mode change.

### Re-run 2026-09-13, after `bench/pools.py` was restored

All four scripts that draw from `pools.py` were re-run end to end against the
published logs (`rerun_*_2026-09-13.log`).

| script | published | re-run |
|---|---|---|
| `genverify_control` | iterative 7/60, direct 36/60 | identical |
| `genverify_corrected` | 36/60, proposer +0 | identical |
| `lane_headroom` | portfolio 37/45, 1 rescued | identical, every arm |
| `verify_budget` | 30 claims, 16 verified, 13 at both 1M and 4M | **31 claims, 16 verified, 13 at 1M, 14 at 4M** |

`verify_budget` did not diverge; its finder changed. The published run used
`hunt18-clean` with `MateMode=true`, and the script was switched to
`MateMode=false` on 2026-09-02, after MateMode was measured as the cause of the
deep deficit. The finder is deterministic (the new setting gave the same 31
claims twice), `MateMode=true` alters 7 of the 39 claims, and every archived
MateProver binary proves the one claim whose cost looked moved in the same
number of nodes. Re-run with `--finder-matemode true`
(`rerun_verify_budget_matemode-on_2026-09-13.log`), the published log is
reproduced exactly: 30 claims, 16 verified, the same six control costs, median
90,362 nodes.

What this changes: with the current finder, 1M verifies one claim fewer than
4M (13 against 14 of 16). "1M verifies as many claims as 4M" holds for the
published claim set and is one claim short on the current one, so read the
ceiling as "1M loses at most one verification in sixteen", not "1M loses none".

## Retracted, and why it is recorded

**Minimality: MateProver 41/60** (vs Matefish, before 2026-09-12) is retracted.
It was 0/60. Every position that solved under that protocol came back marked
`via`, 60 of 60 - a restricted portfolio lane searches the requested depth
directly and proves "a mate within N", never "the shortest mate is N", and the
harness counted any reported depth. So the lane that could answer was outrun on
every position by lanes that could not. The figure was not an overstatement of
a real measurement; there was no measurement. Re-run with `--no-portfolio` on
that lane alone, the honest number is 14/60. The failure shape is the one at 98
and 61: a result that is sound for the question a restricted lane IS asked,
counted against a question it is not.

The +24 finder-lane figure, "MateHunter is behind Huntsman", "Matefish is a
weak proposer", and the −998 x=5 record were each retracted here. Each was a
two-variable comparison, a default left off, or a bound calibrated on the
previous ply. They are kept in the logs because the failure shapes are the
content of this benchmark's rules.
