# Clocks, profiles and Huntsman: results

Run 2026-09-17 under `PLAN.md`, committed before any engine ran at these clocks
except the runs it names as already done. The 30 run logs are in `logs/`:
`all_*` pairs the recommended profile against the other three engines, `kd_*` the
king-danger evaluator against Stockfish 19, and `hs_*` Huntsman 1 against
Stockfish 19.

Finding track, verified claims, one thread per search, 8 searches at a time,
verification by MateProver 0.2.0 at 1,000,000 nodes. **No claim by any engine
was refuted, and every search ended normally.** "+A/-B" pairs the first engine
named against the second: positions only the first verified, positions only the
second verified; p is the two-sided sign test. REC is MateHunter 19's recommended
profile, KD its king-danger evaluator, SF stock Stockfish 19, HS Huntsman 1.

## Mate in 9 to 11, 993 positions

| clock | SF | REC | KD | HS | REC vs SF | KD vs SF | REC vs KD | HS vs REC | HS vs SF |
|---|---:|---:|---:|---:|---|---|---|---|---|
| 500 ms | 293 | 215 | 285 | 630 | +86/-164, p < 0.0001 | +99/-107, p = 0.63 | +84/-154, p < 0.0001 | +440/-25 | +363/-26 |
| 1 s | 411 | 374 | 411 | 695 | +100/-137, p = 0.019 | +115/-115, p = 1.0 | +108/-145, p = 0.023 | +355/-34 | +322/-38 |
| 2 s | 473 | 524 | 484 | 741 | +143/-92, p = 0.0011 | +125/-114, p = 0.52 | +137/-97, p = 0.011 | +256/-39 | +300/-32 |
| 5 s | 585 | 650 | 620 | 776 | +125/-60, p < 0.0001 | +111/-76, p = 0.013 | +93/-63, p = 0.020 | +157/-31 | +210/-19 |
| 10 s | 645 | 691 | 670 | 795 | +99/-53, p = 0.0002 | +90/-65, p = 0.054 | +74/-53, p = 0.076 | +122/-18 | +162/-12 |

Every Huntsman comparison in this table is p < 0.0001.

## Mate in 6 to 8, 1,171 reachable positions

| clock | SF | REC | KD | HS | REC vs SF | KD vs SF | REC vs KD | HS vs REC | HS vs SF |
|---|---:|---:|---:|---:|---|---|---|---|---|
| 500 ms | 719 | 699 | 749 | 908 | +121/-141, p = 0.24 | +139/-109, p = 0.065 | +97/-147, p = 0.0017 | +270/-61 | +257/-68 |
| 1 s | 844 | 844 | 878 | 972 | +103/-103, p = 1.0 | +109/-75, p = 0.015 | +71/-105, p = 0.013 | +178/-50 | +183/-55 |
| 2 s | 914 | 929 | 941 | 1,011 | +87/-72, p = 0.27 | +79/-52, p = 0.023 | +69/-81, p = 0.37 | +132/-50 | +140/-43 |
| 5 s | 984 | 1,003 | 1,014 | 1,049 | +59/-40, p = 0.070 | +58/-28, p = 0.0016 | +37/-48, p = 0.28 | +70/-24 | +87/-22 |

Every Huntsman comparison in this table is p < 0.0001.

## Question 1: where the recommended profile overtakes stock, and which profile to use

**Crossover: 2 seconds.** On mate in 9 to 11 the recommended profile is behind
Stockfish 19 at 500 ms and 1 s, and ahead at 2 s (+143/-92, p = 0.0011), 5 s and
10 s, and it is not behind at any clock longer than 2 s. By the plan's
definition the crossover is 2 s, somewhere between 1 and 2 seconds a position on
this machine.

**Profile advice on mate in 9 to 11,** by the plan's rule:

| clock | better profile | evidence |
|---|---|---|
| 500 ms | king-danger | +154/-84, p < 0.0001 |
| 1 s | king-danger | +145/-108, p = 0.023 |
| 2 s | recommended | +137/-97, p = 0.011 |
| 5 s | recommended | +93/-63, p = 0.020 |
| 10 s | level | +74/-53, p = 0.076 |

On mate in 6 to 8 the pattern is the same at short clocks (king-danger ahead at
500 ms and 1 s) and level at 2 and 5 s. The king-danger evaluator is also the only
profile ahead of stock at mate in 6 to 8, at 1, 2 and 5 s; the recommended profile
never is there.

## Question 2: Huntsman 1 at equal time

**Huntsman 1 is far ahead.** In the primary comparison, 5 s on mate in 10 and 11
(304 positions; `all_d10-11_5000ms.log`), Huntsman verified 248 against the
recommended profile's 180 and Stockfish 19's 161: **+74/-6 against the
recommended profile, p < 0.0001**, and +89/-2 against stock. It leads every other
engine at every clock on both ranges, always at p < 0.0001, and its margin is
widest at short clocks: at 500 ms on mate in 9 to 11 it verified 630 of 993
against 293 for stock and 215 for the recommended profile.

At equal nodes (`studies/depth/`) Huntsman also led from mate in 6, so the lead
does not come from searching faster per node. None of its claims here was
refuted.

## What this changes

1. **For MateHunter:** its out-of-sample advantage over stock is real from about
   2 seconds a position on mate in 9 to 11, and its default profile is the wrong
   one below that; the king-danger evaluator is the better choice at short clocks
   and at mate in 6 to 8. Neither profile comes near Huntsman 1 at any clock
   measured.
2. **For the benchmark:** Huntsman 1 is the strongest UCI mate finder measured on
   positions no engine was tuned on, and it is the engine a new entrant should be
   compared with.

About fifty comparisons are reported here. The Huntsman results and the
crossover rest on p < 0.002 or far smaller; single secondary results near
p = 0.02 (the profile advice at 1 s, 2 s and 5 s) are weaker evidence, though
each fits the pattern across clocks.

## Limits

- Clock results belong to this machine (AMD Ryzen 9 7945HX, 16 cores, WSL2) at 8
  concurrent searches; the crossover in seconds will move on other hardware.
- The positions descend from random checkmates, not composed problems, and stop
  at mate in 11.
- Huntsman 1 is an older Stockfish derivative; how a current Stockfish with a
  comparable mate search would fare is not measured.
