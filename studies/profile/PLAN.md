# MateHunter's profiles under a clock: plan

Written 2026-09-17, before any engine ran under a clock on these positions.

## Why

Every out-of-sample comparison so far (`rounds/round-1/`, `studies/depth/`) used
node budgets, which compare search per node. MateHunter's recommended profile
skips the NNUE evaluation and searches far more nodes per second. Measured on
12 positions at mate in 9 and 10 from `corpora/generated-deeper.epd`, 3,000,000
nodes each, one thread, median nodes per second:

| engine | nodes per second |
|---|---:|
| Stockfish 19 | 1,480,042 |
| MateHunter 19, recommended profile | 4,038,152 |
| MateHunter 19, king-danger evaluator | 3,329,751 |
| MateHunter 19, every mate option off | 1,489,595 |

At equal nodes the recommended profile had about a third of Stockfish's time.
Whether it is behind at equal time is untested out of sample, and that decides
whether the default profile should stay.

## Positions

Already committed by hash: `corpora/generated-deep.epd`
(`9b3f453d045a774ac6bc09dc7babff3be86ee9126535cdac870c8fbb40152250`), mate in 6 to
8, 1,190 positions; `corpora/generated-deeper.epd`
(`bd3a9da6c2556e16ec2c7be1d3e1fbbb4456d2ac877503064118c0754dcf921a`), mate in 9 to
11, 993 positions.

## Measurement, fixed now

- **Arms:** `manifests/stockfish-19.json`, `manifests/matehunter-19.json`
  (recommended profile) and `manifests/matehunter-19-kingdanger.json` (the same
  binary with `MateEvalNull=false`). Every mate option off is not run: it matches
  stock Stockfish 19's `bench` exactly.
- **Runner:** `bench/submit.py` with `--movetime`, one thread per search, 8
  searches at a time on a 16-core machine with nothing else running, MateProver
  0.2.0 verification at 1,000,000 nodes.
- **Runs:**
  1. mate in 9 to 11, 5,000 ms, then mate in 10 and 11 alone and mate in 9 alone
     from the same results;
  2. mate in 6 to 8, 1,000 ms;
  3. mate in 9 to 11, 1,000 ms.

## What would count

The primary comparison is the recommended profile against Stockfish 19 at 5,000
ms on mate in 10 and 11 together, the range and clock of MateHunter's ChestUCI
claim (606 against 324 at mate in 14 and more, 1,244 against 715 at 10 to 13).

- **Ahead, p < 0.05:** the recommended profile finds more mates than stock in
  equal time out of sample; recommend keeping it as the default, and stating
  that node budgets understate it.
- **Behind, p < 0.05:** recommend that the default become every mate option off,
  which is stock Stockfish 19, in a major version, with the profile kept as an
  option.
- **Neither:** recommend keeping the default, with the documentation saying that
  out of sample it has not been shown to beat stock at equal time.

The king-danger evaluator against the recommended profile, the other depths and
the 1,000 ms clock are secondary, and would change the recommendation only if
the king-danger evaluator is ahead of both at p < 0.05.
