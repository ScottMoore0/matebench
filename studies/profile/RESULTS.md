# MateHunter's profiles under a clock: results

Run 2026-09-17 under `PLAN.md`, committed before any engine ran under a clock on
these positions. Logs are in `logs/`.

Finding track, verified claims, one thread per search, verification by
MateProver 0.2.0 at 1,000,000 nodes. No claim by any engine was refuted.
"+A/-B" pairs the first engine named against the second: positions only the
first verified, positions only the second verified; p is the two-sided sign
test. "Recommended" is `manifests/matehunter-19.json`, "king-danger"
`manifests/matehunter-19-kingdanger.json`.

## The pre-registered comparison: 5,000 ms, mate in 10 and 11

| run | positions | Stockfish 19 | recommended | king-danger | recommended vs Stockfish | king-danger vs Stockfish | recommended vs king-danger |
|---|---:|---:|---:|---:|---|---|---|
| 8 searches at a time | 304 | 161 | 180 | 181 | **+39/-20, p = 0.018** | +38/-18, p = 0.011 | +24/-25, p = 1.0 |
| replication, 4 at a time | 304 | 162 | 184 | 185 | **+42/-20, p = 0.007** | not paired | +23/-24, p = 1.0 |

**Against the criterion stated in advance: the recommended profile is ahead of
Stockfish 19, p < 0.05.** The replication, run afterwards at half the
concurrency with its own cache, agrees. By the plan the recommendation is to
keep it as the default and to state that node budgets understate it. The margin
is far smaller than on ChestUCI, where the same clock gave 1,244 against 715 at
mate in 10 to 13: here about 12% more mates, there 74%.

## Secondary

| positions | clock | Stockfish 19 | recommended | king-danger | recommended vs Stockfish | king-danger vs Stockfish | recommended vs king-danger |
|---|---|---:|---:|---:|---|---|---|
| mate in 9, 689 | 5,000 ms | 424 | 470 | 439 | +86/-40, p = 0.0001 | +73/-58, p = 0.22 | +69/-38, p = 0.004 |
| mate in 9 to 11, 993 | 5,000 ms | 585 | 650 | 620 | +125/-60, p < 0.0001 | not run | +93/-63, p = 0.02 |
| mate in 9 to 11, 993 | 1,000 ms | 411 | 374 | 411 | +100/-137, p = 0.019 | +115/-115, p = 1.0 | +108/-145, p = 0.023 |
| mate in 6 to 8, 1,190 | 1,000 ms | 844 | 844 | 878 | +103/-103, p = 1.0 | +109/-75, p = 0.015 | +71/-105, p = 0.013 |

The 1,190 positions at mate in 6 to 8 include 19 that no game can reach
(`studies/depth/RESULTS.md`); Stockfish and both MateHunter profiles refuse them
alike, so no comparison above changes without them.

1. **The advantage depends on the clock.** At 5 seconds the recommended profile
   is ahead of stock at mate in 9, 10 and 11. At 1 second it is level at mate in
   6 to 8 and behind at 9 to 11.
2. **The king-danger evaluator is the better profile at 1 second**, ahead of the
   recommended profile at both depth ranges and ahead of stock at mate in 6 to 8.
   At 5 seconds it is level with the recommended profile at mate in 10 and 11 and
   behind it at mate in 9.
3. **Node budgets hid all of this.** At 10,000,000 nodes
   (`studies/depth/`) the recommended profile was never ahead. It searches about
   2.7 times as many nodes per second as Stockfish 19, so a node budget gave it
   roughly a third of Stockfish's time.

By the plan's secondary rule, the king-danger evaluator is ahead of both others
only at 1,000 ms on mate in 6 to 8, not in the primary comparison, so it does not
change the recommendation. It is the stronger choice for short clocks.

## Limits

- A clock result belongs to this machine (AMD Ryzen 9 7945HX, 16 cores, WSL2)
  and its load; the replication at half the concurrency is the check on load.
- The positions descend from random checkmates, not composed problems.
- Mate in 12 and deeper, and clocks other than 1 and 5 seconds, are untested.
