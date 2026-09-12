# Reference results

Every number below was produced by a script in `bench/` and the raw log is in
this directory, dated. Where a result is *not established* it says so. Read the
configuration column: two of these engines are measured at settings that are
not their defaults, because their defaults switch the mate solver off.

## Engines and configurations

**What a third party can obtain.** MateProver is public and pinned below.
Chest, Matefish and Huntsman are distributed by their own authors, and the
table below says where. **MateHunter is not distributed**: it is a private
Stockfish fork, so every row naming it is recorded for the protocol's sake and
cannot be reproduced by anyone else. The tracks and budgets do not depend on
it.

| engine | base | manifest used | notes |
|---|---|---|---|
| MateProver 0.1.0 | own DFPN | defaults; `--direct-depth` on finding tracks, `--iterative-depth` on minimality | emits certificates; MIT, https://github.com/ScottMoore0/mateprover at tag v0.1.0 |
| MateHunter 18 | Stockfish 18 fork | `MateEval=true`, `MateMode=false` | shipped default as of 2026-09-02; `MateMode=true` costs 21/234 at d26+ |
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
