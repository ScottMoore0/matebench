# Why does Huntsman 1 win? Plan

Written 2026-09-19, before the runs below.

## What is already known

On generated positions no engine was tuned on (`studies/clock/`, `studies/depth/`),
Huntsman 1 leads every other engine at every clock and from mate in 6 at equal
nodes: +74/-6 against MateHunter 19's recommended profile at 5 s on mate in 10
and 11. It is not speed. On twelve positions at mate in 9 and 10, 3,000,000
nodes, one thread, median nodes per second:

| engine | nps |
|---|---:|
| MateHunter 19, recommended | 4,032,724 |
| MateHunter 19, king-danger | 3,602,162 |
| Huntsman 1 | 2,305,960 |
| Huntsman 1, MateSearch off | 2,416,098 |
| Stockfish 19 | 1,445,813 |
| MateHunter 19, every mate option off | 1,533,304 |

Huntsman searches at 57% of MateHunter's rate and wins anyway, so it searches
better per node.

Huntsman differs from a modern Stockfish in two ways at once, and the question
is which one matters:

1. **Its evaluation.** `MateSearch` returns `vk`, Stockfish's classical
   king-safety term alone (`king<WHITE>() - king<BLACK>()`, phase-interpolated),
   including the quadratic danger transform and pawn shelter and storm.
   MateHunter's king-danger evaluator is a different, hand-written function.
2. **Its search.** Its base predates years of Stockfish pruning and reduction
   tuning, all of it aimed at winning games rather than forcing mate.

## The design

A two-by-two: old search or new search, mate evaluation or ordinary evaluation.

| | ordinary evaluation | mate evaluation |
|---|---|---|
| **old search** (Huntsman) | `huntsman-1-nomate.json` | `huntsman-1.json` |
| **new search** (Stockfish 19) | `stockfish-19.json` | `matehunter-19.json`, `matehunter-19-kingdanger.json` |

Three of the four cells are already measured on `corpora/generated-deeper.epd`
at mate in 9 to 11. This adds the missing one, Huntsman with `MateSearch=false`,
and one further arm, `matehunter-19-matemode.json`, which is the recommended
profile with razoring, futility and null-move pruning switched off: if modern
pruning is what costs the new search, switching it off should recover part of
the gap.

- **Positions:** `corpora/generated-deeper.epd`, mate in 9 to 11, 993 positions,
  sha256 `bd3a9da6c2556e16ec2c7be1d3e1fbbb4456d2ac877503064118c0754dcf921a`.
- **Budgets:** 10,000,000 nodes, and a 5,000 ms clock, 8 searches at a time.
- **Verification:** MateProver 0.2.0 at 1,000,000 nodes, as everywhere else.

## What would count

- **The evaluation is the cause** if Huntsman with MateSearch off falls back to
  about Stockfish 19's level, and the gap between Huntsman on and off is of the
  same size as Huntsman's lead over MateHunter. Then porting `vk` into Stockfish
  19 is worth its cost.
- **The search is the cause** if Huntsman with MateSearch off still beats
  Stockfish 19 by most of that lead. Then a ported evaluation will not close the
  gap, and the work is in the search.
- **Both** if each contributes a part, which the two comparisons will size
  separately.
- **MateMode** tells us whether the part attributable to the search is the three
  prunings it switches off, or something else.
