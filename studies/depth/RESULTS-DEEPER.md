# Mate in 9 to 11: results

Run 2026-09-17 under `PLAN-DEEPER.md`, committed before any engine ran on these
positions. The 12 run logs are in `logs-deeper/`.

Finding track, verified claims, one thread, verification by MateProver 0.2.0 at
1,000,000 nodes. No claim by any engine was refuted, and every search ended
normally. "+A/-B" pairs the first engine named against the second: positions
only the first verified, positions only the second verified; p is the two-sided
sign test.

## The pre-registered comparison: 10,000,000 nodes

| mate in | positions | MateHunter 19 | Stockfish 19 | Huntsman 1 | MateHunter vs Stockfish | MateHunter vs Huntsman |
|---|---:|---:|---:|---:|---|---|
| 9 | 689 | 436 | 455 | 537 | +50/-69, p = 0.10 | +17/-118, p < 0.0001 |
| 10 | 253 | 147 | 150 | 204 | +25/-28, p = 0.78 | +5/-62, p < 0.0001 |
| 11 | 51 | 22 | 31 | 44 | +0/-9, p = 0.004 | +0/-22, p < 0.0001 |
| **10 and 11** | **304** | **169** | **181** | **248** | **+25/-37, p = 0.16** | **+5/-84, p < 0.0001** |

**Against the criterion stated in advance: no balance favours MateHunter at mate
in 10 and 11.** It is +25/-37 against Stockfish 19, the wrong way and not
significant. On ChestUCI in the same range MateBench measured MateHunter
+478/-59. By the plan this is evidence against depth explaining the ChestUCI gain
at mate in 10 and 11. It cannot exclude a gain that begins at mate in 12 or
deeper.

On reported claims, before verification, the picture is the same: +30/-48 at
mate in 10 and 11 (p = 0.05). Verification at 1,000,000 nodes left 15
MateHunter claims, 21 Stockfish claims and 29 Huntsman claims unconfirmed there,
none refuted.

## Smaller budgets, secondary

| mate in | 100,000: MH / SF / HS | MH vs SF | MH vs HS | 10,000: MH / SF / HS |
|---|---|---|---|---|
| 9 | 7 / 70 / 211 | +2/-65 | +1/-205 | 0 / 3 / 1 |
| 10 | 0 / 13 / 65 | +0/-13 | +0/-65 | 0 / 0 / 0 |
| 11 | 0 / 6 / 8 | +0/-6 | +0/-8 | 0 / 0 / 0 |
| 10 and 11 | 0 / 19 / 73 | +0/-19, p < 0.0001 | +0/-73, p < 0.0001 | 0 / 0 / 0 |

At 10,000 nodes almost nothing is solved at these depths by any engine.

## Across both studies

At 10,000,000 nodes, MateHunter 19 against Stockfish 19 on generated positions
no engine could have been tuned on, one mate length at a time (`RESULTS.md` for
mate in 1 to 8):

| mate in | 1-5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|
| MateHunter vs Stockfish | within 1 or 2 | +3/-20 | +13/-25 | +13/-23 | +50/-69 | +25/-28 | +0/-9 |

At no depth from mate in 1 to 11 is MateHunter ahead. Huntsman 1 is ahead of
both from mate in 6.

## What this does and does not show

- **Shown:** up to mate in 11, the ChestUCI advantage of MateHunter 19 does not
  appear on generated positions, at any budget, including mate in 10 and 11,
  the range where ChestUCI showed it.
- **Not shown:** anything about mate in 12 and deeper, or about composed
  problems. These positions descend from random checkmates. What remains to
  explain the ChestUCI gain is tuning on matetrack, the kind of position, or
  both; these studies cannot separate them.
