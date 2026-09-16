# Reference results

Every number below was produced by a script in `bench/` and the raw log is in
this directory, dated. Where a result is *not established* it says so. Read the
configuration column: two of these engines are measured at settings that are
not their defaults, because their defaults switch the mate solver off.

## Engines and configurations

**What a third party can obtain.** MateProver is public and pinned below.
Chest, Matefish, Huntsman and Stockfish are distributed by their own authors,
and the table below says where. **MateHunter 19 is public** as MateHunter 0.1.0:
GPL-3, a patch against Stockfish 19, https://github.com/ScottMoore0/matehunter at
tag v0.1.0. Its rows here were measured with the development build, whose search
the release reproduces: `bench` reports the same node count under 13 option
settings covering every option the release keeps. MateHunter 18 is not
distributed, so its rows are recorded for the protocol's sake and cannot be
reproduced by anyone else. The tracks and budgets do not depend on either.

| engine | base | manifest used | notes |
|---|---|---|---|
| MateProver 0.2.0 | own DFPN | defaults; `--direct-depth` on finding tracks, `--iterative-depth` on minimality | emits certificates; MIT, https://github.com/ScottMoore0/mateprover at tag v0.2.0. Search unchanged from 0.1.0: with the portfolio off, output is byte-identical to 0.1.0 on 30 ChestUCI positions in both modes, and `genverify_control` reproduces exactly. With the portfolio on, lanes race, so lines and node counts vary run to run in both versions while solved positions and mate lengths do not |
| MateHunter 18 | Stockfish 18 fork | `MateEval=true`, `MateMode=false` | shipped default as of 2026-09-02; `MateMode=true` costs 21/234 at d26+ |
| MateHunter 19 | Stockfish 19 fork | `MateEval=true`, `MateMode=false`, every other mate option set off explicitly | port of the 18 fork; with every mate option off it is node-for-node identical to stock (bench 2,497,913). Recommended profile from 2026-09-13 adds `MateEvalNull=true`, and is the engine's default from the same date; see "Recommended profile" |
| Stockfish 19 | own (NNUE) | defaults with `Threads=1`, `Hash=256` | https://stockfishchess.org; built from the release source with the fork's compiler and flags |
| Huntsman 1 | Stockfish fork | `MateSearch=true` (its default) | recorded as over-claiming and echoing toward the bound, though none of the 298 of its claims re-proved on 2026-09-14 was refuted; by joergoster, https://github.com/joergoster/Stockfish-old/releases/tag/h1 (the binary used self-identifies as `The Huntsman 1`) |
| Matefish 170826 | Stockfish + PNS | `ProofNumberSearch=true`, `PNS Hash=4096` | **both default off/small**; at defaults it abandons a d14 search in 0.2 s |
| Chest 3.19 | own | `WinChest.exe`, job on stdin, 2048 MB, `UseDatabase=false` | 1999-era; endgame databases off (they reach ~1% of proof nodes here). **Not `ChestUCI.exe`**: that is the GUI/UCI wrapper, and fed a job it spins with no output, which a harness scores as a timeout |

## Finding, verified - MateProver vs Matefish (`vs_matefish_v020_2026-09-13.log`)

60 positions, d8–16, 10 s each, single-threaded. Claims verified by MateProver
`--direct-depth`. Re-measured 2026-09-13 with MateProver 0.2.0; the 2026-09-12
run with 0.1.0 (`vs_matefish_2026-09-12.log`) used the same protocol, and the
minimality row of the run before that was not measuring minimality, see the
retraction below.

| band | n | MateProver | Matefish claimed | Matefish verified |
|---|---|---|---|---|
| d8 | 12 | 10 | 10 | 10 |
| d10 | 12 | 10 | 11 | 10 |
| d12 | 12 | 10 | 10 | 9 |
| d14 | 12 | 8 | 8 | 6 |
| d16 | 12 | 8 | 7 | 7 |
| **total** | **60** | **46** | 46 | **42** |

Paired: Matefish +0/−4, 4 discordant, **p = 0.125 - parity, not established
either way**. The 0.1.0 run gave 45 and 41 with the same paired result: one d14
position for each engine sits on the edge of the 10-second clock.

**Minimality: MateProver 14/60**, by band 7/3/3/1/0 across d8–d16; Matefish n/a
(echoes the bound). The minimality lane runs `--no-portfolio`: a restricted
lane searches the requested depth directly and cannot establish a shortest
mate, so leaving the portfolio on spends the budget on lanes that are
structurally unable to answer.

Speed on the 42 both solved: MateProver faster on 36, p < 0.0001, median 2.90×
(3.84× in the 0.1.0 run; a wall-clock ratio moves with machine load, so it is
not compared across runs).
**This row is not comparable with the pre-2026-09-12 one.** The script that
produced the earlier speed figure is not in the tree and its method cannot be
recovered, and this run was taken under WSL rather than natively. The counts
above are proof counts and are platform-independent; these two numbers are wall
clock and are not.

## Finding - MateHunter 18 vs Huntsman, 2026-09-02 (`h2h_chestuci_*.log`, `h2h_deep_*.log`)

ChestUCI corpus, 10M nodes, 1 thread, paired. **In-sample for MateHunter:** ChestUCI is
almost entirely contained in matetrack, which MateHunter was tuned on (see "ChestUCI is
not independent of matetrack" below).

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

## Finding - MateHunter 19 vs Huntsman 1 (`vs_huntsman_*_2026-09-14.log`, `verify_claims_*_huntsman_2026-09-14.log`)

ChestUCI, all 2,477 positions at d10+, 10M nodes, one thread, paired, with
Huntsman at `MateSearch=true` as in the Stockfish 18 comparison above.
In-sample for MateHunter: 2,460 of these 2,477 positions are in matetrack.

| positions | MateHunter 19, recommended | MateHunter 19, full evaluator | Huntsman 1 | Stockfish 19 |
|---|---|---|---|---|
| d14+, 953 | **590** | 586 | 542 | 343 |
| d10–13, 1,524 | **1,225** | 1,176 | 1,101 | 757 |

On reported mates, the recommended profile against Huntsman is +131/−83 at d14+
(p = 0.0013) and +239/−115 at d10–13 (p < 0.0001). By band at d14+: d14–17
+71/−28, d18–21 +28/−17 (p = 0.14), d22–25 +15/−10, d26–30 +6/−11, d31+ +11/−17,
none of the last three below p = 0.3.

**Claims re-proved** (`bench/verify_claims.py`: MateProver 0.2.0 `--direct-depth
--no-portfolio` at the claimed length, 20M nodes): every claim only one engine
made, and a seeded sample of 100 both made.

| claims | verified | refuted | unconfirmed |
|---|---|---|---|
| MateHunter 19 only, 370 | 220 | 0 | 150 |
| Huntsman only, 198 | 97 | 0 | 101 |
| both made, 100 (MateHunter / Huntsman) | 74 / 73 | 0 / 0 | 26 / 27 |

On verified discordant claims only: **+220/−97 (p < 0.0001)** - d10–13 +177/−73,
d14–17 +31/−8 (p = 0.0003), d18–21 +9/−9, d22+ +3/−7. The full king-danger
evaluator gives the same picture: +193/−105 verified (+132/−88 reported at d14+,
+198/−123 at d10–13).

1. **MateHunter 19 is clearly ahead of Huntsman from mate in 10 to 17**, on
   reported and verified claims alike.
2. **From mate in 18 it is level**, and from mate in 26 Huntsman reports slightly
   more mates, not significantly. Too few claims that deep verify within budget
   to say more.
3. **No claim by either engine was refuted.** Huntsman's recorded over-claiming did
   not appear under this protocol (node-limited `go mate N`, scored 0 < dm <= N),
   and the unconfirmed share is about the same for both engines, so verification
   favours neither.

## Finding - MateHunter 19 vs stock Stockfish 19 (`vs_stockfish_2026-09-12.log`)

ChestUCI, all 953 positions at d14+, 10M nodes, 1 thread, paired. In-sample for
MateHunter: 943 of these 953 positions are in matetrack. MateHunter is a Stockfish 19 derivative on the same source,
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

### Replication on positions the run above did not use (`vs_stockfish_d10-13_2026-09-13.log`)

ChestUCI d10–13, 1,524 positions the run above did not use, same budget and arms.
This replication is out of sample for the d14+ run only. It is not out of MateHunter's
tuning data: 1,517 of the 1,524 positions are in matetrack.

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
exactly. Since 2026-09-13 it is also the engine's default (bench at defaults
5,314,178 nodes; with every mate option off, still stock's 2,497,913). The
harness sets every toggle
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

## Tablebase positions as a corpus - pilot (`dtm_pilot_2026-09-13.log`, `vs_stockfish_dtm_pilot_2026-09-13.log`)

`docs/HELDOUT.md` needs a pool with exact depths and free terms. A DTM tablebase
gives exact depths with no search, so the question was whether its positions
measure the same thing as composed problems. `bench/dtm_pilot.py` drew 526
positions from the 3-4 man Gaviota tables present locally (six materials, mate
in 10 to 35, at most 40 per material and depth band), and each engine ran them
at the same budget it used on ChestUCI d10+.

Ground truth holds: on 40 sampled positions MateProver's proved shortest mate
equals the tablebase depth on all 24 it finished, none shorter and none longer;
16 did not finish at 64M nodes.

| engine | ChestUCI d10+ (2,477) | tablebase pilot (526) |
|---|---|---|
| MateProver, `--direct-depth`, 4M nodes | **70.9%** | 36.9% |
| MateHunter 19, recommended profile, 10M nodes | 73.3% | 53.8% |
| Stockfish 19, 10M nodes | 44.4% | **60.3%** |

Paired, MateProver against Stockfish 19 is +851/−196 on ChestUCI and +11/−134
on the tablebase set; MateHunter against Stockfish 19 is +803/−88 on ChestUCI and
+30/−64 on the tablebase set.

| material | positions | MateProver | MateHunter | Stockfish 19 |
|---|---|---|---|---|
| KQvKR | 160 | 39 | 55 | 71 |
| KRvKR | 120 | 44 | 77 | 96 |
| KBBvK | 120 | 25 | 46 | 42 |
| KRvK | 80 | 40 | 61 | 62 |
| KQvKQ | 40 | 40 | 38 | 40 |
| KQvK | 6 | 6 | 6 | 6 |

1. **The ranking reverses.** Both engines that lead on composed problems trail on
   tablebase endgames, and the engine last on ChestUCI is first here.
2. **MateProver is hit hardest beyond mate in 13:** 17 of 160 at d14–17 and 0 of
   120 at d18–21, against MateHunter's 87 and 19. Its source already notes that
   proof numbers carry no signal with this little material; this measures it on
   directmate.
3. **Stockfish 19's lead is where the defender keeps a piece** (KRvKR, KQvKR),
   the endgames in which NNUE's knowledge of the material decides the line.

**Verdict: not fit for the held-out pool**, and `docs/HELDOUT.md` now says so.
Budgets differ between engines, but each engine had the same budget on both
corpora, so the reversal belongs to the positions. Five-man tables would add
material variety but would not turn a reversal this large around, so they are
not needed for this decision.

## ChestUCI is not independent of matetrack (2026-09-16)

Until 2026-09-16 this document and `corpora/PROVENANCE.md` described ChestUCI as a
corpus neither engine was tuned on, and used it as held-out data for MateHunter. It
is not. Comparing the first four FEN fields of the two files:

| ChestUCI band | positions | also in matetrack |
|---|---|---|
| d1-9 | 4,068 | 4,066 |
| d10-13 | 1,524 | 1,517 |
| d14-17 | 449 | 447 |
| d18-21 | 186 | 184 |
| d22-25 | 84 | 84 |
| d26-30 | 65 | 65 |
| d31+ | 169 | 163 |
| **all** | **6,545** | **6,526 (99.7%)** |

6,442 of the shared positions carry the same mate length in both files. matetrack
is built from its own copy of the ChestUCI suite (`ChestUCI_23102018.epd`), which is
why; `corpora/PROVENANCE.md` already recorded that the two ChestUCI files differ by
about fifty positions, and missed that matetrack contains nearly all of the rest.

The overlap came to light when `bench/submit.py`, told that MateHunter was tuned on
matetrack, removed 447 of the 449 ChestUCI positions at d14-17 from a run.

**What it changes.** Every MateHunter result on ChestUCI above is in-sample: the
MateHunter 18 and 19 comparisons with Huntsman, the comparison with stock Stockfish 19
and its d10-13 replication, the channel and consumer arms, and the recommended
profile. None of them shows that the gain carries to positions MateHunter has not
seen. They remain correct measurements of what they measured, on the positions they
used, and the verification counts stand: a certified mate is a mate whatever corpus
it came from.

**What does not change.** Results on engines not tuned on matetrack are not in-sample
for that reason. matetrack was built to track Stockfish's mate finding, and
MateProver's certificate corpus is drawn from matetrack, so neither can be called
unexposed either. Chest 3.19 predates both corpora.

**Re-measured.** MateHunter 19, Stockfish 19 and Huntsman 1 are measured on generated
positions that no engine could have seen, in held-out round 1
(`rounds/round-1/`) and on that round's development split below.

## Out of sample: held-out round 1 (`rounds/round-1/`)

MateHunter 19 (recommended profile), Stockfish 19 and Huntsman 1 on 4,934
generated positions, disjoint from matetrack and ChestUCI by construction and
generated after all three binaries were built: a salted 20% held out (972) and
the development split (3,962). Budgets and comparisons were committed before any
engine ran. Finding track, verified claims, one thread; no claim was refuted.

| set, budget | MateHunter 19 | Stockfish 19 | Huntsman 1 | MateHunter vs Stockfish | MateHunter vs Huntsman |
|---|---:|---:|---:|---|---|
| held out, 10,000,000 | 963 | 963 | 971 | +5/-5, p = 1.0 | +0/-8, p = 0.0078 |
| held out, 100,000 | 815 | 872 | 914 | +14/-71, p < 0.0001 | +6/-105, p < 0.0001 |
| held out, 10,000 | 642 | 767 | 801 | +3/-128, p < 0.0001 | +2/-161, p < 0.0001 |
| development, 10,000,000 | 3,935 | 3,938 | 3,956 | +12/-15, p = 0.70 | +3/-24, p < 0.0001 |
| development, 100,000 | 3,320 | 3,570 | 3,727 | +57/-307, p < 0.0001 | +29/-436, p < 0.0001 |
| development, 10,000 | 2,619 | 3,118 | 3,269 | +25/-524, p < 0.0001 | +10/-660, p < 0.0001 |

1. **The ChestUCI advantage of MateHunter 19 over stock Stockfish 19 does not
   appear on these positions.** Level at 10,000,000 nodes on both sets; behind at
   100,000 and 10,000 on both, at p < 0.0001.
2. **Huntsman 1 leads both engines** at every budget on both sets.
3. **Not established: why.** Tuning on matetrack, the pool's depth (none deeper
   than mate in 9, against a ChestUCI gain measured from mate in 10) and the kind
   of position (descended from random checkmates, which the tablebase pilot
   suggests can reverse rankings) all remain. `rounds/round-1/CLOSE.md` gives the
   per-band detail and what would separate them.

**Depth, up to mate in 8** (`studies/depth/`). A pre-registered follow-up on
2,428 further generated positions, measured one mate length at a time, found no
depth at which MateHunter 19 finds more mates than Stockfish 19: at 10,000,000
nodes +13/-23 at mate in 8 (p = 0.13), behind from mate in 6, and behind at every
depth from mate in 2 at 100,000 and 10,000 nodes. Huntsman 1 leads both from mate
in 6. That counts against depth as the explanation up to mate in 8, and says
nothing about mate in 10 and deeper, which generation has not yet reached.

Until that is settled, treat the recommended profile, and every MateHunter
result above, as established on ChestUCI only.

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
