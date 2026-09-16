# Does MateHunter's advantage grow with depth? Results

Run 2026-09-16 to 2026-09-17 under `PLAN.md`, committed before any engine ran on
these positions. The 24 run logs are in `logs/`, one per mate length and budget.

Finding track, verified claims, one thread, verification by MateProver 0.2.0 at
1,000,000 nodes. No claim by any engine was refuted. "+A/-B" pairs the first
engine named against the second: positions only the first verified, positions
only the second verified; p is the two-sided sign test.

## The pre-registered comparison: 10,000,000 nodes

| mate in | positions | MateHunter 19 | Stockfish 19 | Huntsman 1 | MateHunter vs Stockfish | MateHunter vs Huntsman |
|---|---:|---:|---:|---:|---|---|
| 1 | 257 | 255 | 255 | 257 | +0/-0 | +0/-2, p = 0.50 |
| 2 | 221 | 210 | 210 | 221 | +0/-0 | +0/-11, p = 0.001 |
| 3 | 244 | 242 | 243 | 244 | +0/-1, p = 1.0 | +0/-2, p = 0.50 |
| 4 | 234 | 231 | 231 | 234 | +0/-0 | +0/-3, p = 0.25 |
| 5 | 282 | 278 | 277 | 282 | +2/-1, p = 1.0 | +0/-4, p = 0.13 |
| 6 | 407 | 373 | 390 | 402 | +3/-20, p = 0.0005 | +3/-32, p < 0.0001 |
| 7 | 486 | 406 | 418 | 438 | +13/-25, p = 0.07 | +6/-38, p < 0.0001 |
| 8 | 297 | 200 | 210 | 233 | +13/-23, p = 0.13 | +11/-44, p < 0.0001 |

**Against the criterion stated in advance: no balance favours MateHunter at mate
in 8.** It is +13/-23 against Stockfish 19, the wrong way and not significant.
From mate in 6, where the two first differ on more than a few positions,
MateHunter is behind at every depth (net -17, -12, -10), with no trend towards an
advantage. By the plan this is
evidence against depth explaining the ChestUCI gain up to mate in 8. It cannot
exclude an effect that begins at mate in 10 or deeper, where the ChestUCI gain
was measured and where these positions do not reach.

Adding round 1's positions at mate in 8 to 12 (44, of which 3 are mate in 9;
`rounds/round-1/CLOSE.md`, held out and development together) gives, at mate in
8 and 9: MateHunter against Stockfish +18/-26 (p = 0.29) and against Huntsman
+11/-51 (p < 0.0001). The round's logs report that band as a whole, so its mates
in 9 cannot be separated out.

## Smaller budgets, secondary

| mate in | 100,000: MH / SF / HS | MH vs SF | MH vs HS | 10,000: MH / SF / HS | MH vs SF | MH vs HS |
|---|---|---|---|---|---|---|
| 1 | 255 / 255 / 257 | +0/-0 | +0/-2 | 255 / 255 / 257 | +0/-0 | +0/-2 |
| 2 | 189 / 210 / 221 | +0/-21 | +0/-32 | 152 / 200 / 220 | +0/-48 | +0/-68 |
| 3 | 211 / 241 / 244 | +1/-31 | +0/-33 | 133 / 207 / 231 | +0/-74 | +0/-98 |
| 4 | 151 / 210 / 233 | +2/-61 | +0/-82 | 55 / 157 / 190 | +1/-103 | +0/-135 |
| 5 | 136 / 220 / 269 | +12/-96 | +4/-137 | 26 / 118 / 145 | +1/-93 | +1/-120 |
| 6 | 79 / 228 / 320 | +4/-153 | +4/-245 | 7 / 71 / 100 | +0/-64 | +0/-93 |
| 7 | 34 / 156 / 233 | +6/-128 | +4/-203 | 0 / 31 / 32 | +0/-31 | +0/-32 |
| 8 | 11 / 44 / 92 | +2/-35 | +0/-81 | 0 / 3 / 6 | +0/-3 | +0/-6 |

Every comparison at these budgets with ten or more discordant pairs is p < 0.0001
against MateHunter. The gap widens with depth: at 100,000 nodes MateHunter solves
11 of 297 mates in 8, Stockfish 44 and Huntsman 92.

## 39 positions no game can reach

39 positions (2, 11, 1, 3, 3, 9, 6 and 4 at mate in 1 to 8) have more material
than a game can produce, such as a side with two queens and eight pawns. The
generator steps back through uncaptures, which add pieces, and python-chess's
validity check does not count promotions. Stockfish 19 and MateHunter 19 refuse
these positions as having too many pieces and exit, which the logs record as a
search that did not end normally; Huntsman 1 accepts them. Round 1's pool has
none, and neither does matetrack; ChestUCI has one.

They cost MateHunter and Stockfish alike, so **every MateHunter against Stockfish
result above is unchanged without them.** They do favour Huntsman. Re-scored from
the same runs on the 2,389 reachable positions, at 10,000,000 nodes MateHunter
against Huntsman is +0/-0 at mate in 1, 2 and 4, +0/-1 at 3 and 5, +3/-23 at 6
(p = 0.0001), +6/-32 at 7 (p < 0.0001) and +11/-41 at 8 (p < 0.0001). Huntsman's
lead from mate in 6 stands; its lead at mate in 2 came entirely from these
positions. The corpus is kept as committed, since its hash was pre-registered.

`bench/generate_corpus.py` now rejects such material, at every step back and in
the synthetic checkmates, so later corpora cannot contain it.

## What this does and does not show

- **Shown:** on 2,428 generated positions no engine could have been tuned on, up
  to mate in 8, MateHunter 19's recommended profile finds no more mates than
  stock Stockfish 19 at 10,000,000 nodes at any depth, and fewer at the smaller
  budgets from mate in 2. Huntsman 1 finds more than both from mate in 6.
- **Not shown:** anything about mate in 10 and deeper, where MateHunter's
  ChestUCI gain was measured. These positions also descend from random
  checkmates, not composed problems, and the kind of position remains a possible
  explanation alongside tuning.
