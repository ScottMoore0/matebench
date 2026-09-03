# Reference results

Every number below was produced by a script in `bench/` and the raw log is in
this directory, dated. Where a result is *not established* it says so. Read the
configuration column: two of these engines are measured at settings that are
not their defaults, because their defaults switch the mate solver off.

## Engines and configurations

| engine | base | manifest used | notes |
|---|---|---|---|
| MateProver 0.1.0 | own DFPN | defaults; `--direct-depth` on finding tracks, `--iterative-depth` on minimality | emits certificates |
| MateHunter 18 | Stockfish 18 fork | `MateEval=true`, `MateMode=false` | shipped default as of 2026-09-02; `MateMode=true` costs 21/234 at d26+ |
| Huntsman 1 | Stockfish fork | `MateSearch=true` (its default) | over-claims; echoes toward the bound |
| Matefish 170826 | Stockfish + PNS | `ProofNumberSearch=true`, `PNS Hash=4096` | **both default off/small**; at defaults it abandons a d14 search in 0.2 s |
| Chest 3.19 | own | `WinChest.exe`, job on stdin, 2048 MB, `UseDatabase=false` | 1999-era; endgame databases off (they reach ~1% of proof nodes here). **Not `ChestUCI.exe`**: that is the GUI/UCI wrapper, and fed a job it spins with no output, which a harness scores as a timeout |

## Finding, verified - MateProver vs Matefish (`vs_matefish_2026-09-02.log`)

60 positions, d8–16, 10 s each, single-threaded, idle machine. Claims verified
by MateProver `--direct-depth`.

| band | n | MateProver | Matefish claimed | Matefish verified |
|---|---|---|---|---|
| d8 | 12 | 10 | 10 | 10 |
| d10 | 12 | 10 | 11 | 10 |
| d12 | 12 | 10 | 10 | 9 |
| d14 | 12 | 7 | 8 | 6 |
| d16 | 12 | 8 | 7 | 7 |
| **total** | **60** | **45** | 46 | **42** |

Paired: Matefish +1/−4, 5 discordant, **p = 0.375 - parity, not established
either way**. Speed on the 41 both solved: MateProver faster on 32, p = 0.0004,
median 1.49×. Minimality: MateProver 41/60; Matefish n/a (echoes the bound).

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
| selfmate | 903 | 318 | 389 (re-measurement under the final protocol in progress) |
| selfstalemate | 76 | 49 | 52 |

## Budgets and gates

- **Verification ceiling** (`verify_budget_2026-08-30.log`): cost bimodal,
  median 90,362 nodes, max 20.4M; 1M verifies as many claims as 4M; derivation
  controlled 6/6 at both ends of the cost range.
- **Ninth portfolio lane** (`lane9_*.log`): at a real lane budget, 1 rescued
  position of 45 at both d10–14 and d16–20. The restriction family is exhausted.
- **Lane-0 weight** (`lane0_sweep_2026-08-30.log`): flat 30–90%.
- **Generate-and-verify** (`genverify_*.log`): **+0** against a correctly
  configured baseline. The earlier "+24" was the mode change.

## Retracted, and why it is recorded

The +24 finder-lane figure, "MateHunter is behind Huntsman", "Matefish is a
weak proposer", and the −998 x=5 record were each retracted here. Each was a
two-variable comparison, a default left off, or a bound calibrated on the
previous ply. They are kept in the logs because the failure shapes are the
content of this benchmark's rules.
