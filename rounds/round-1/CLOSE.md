# Held-out round 1: disclosure and results

Closed 2026-09-16. Opened by `OPEN.md`, which fixed the salt, the pool, the
split, the engines, the budgets and the comparisons before any engine ran.

## Disclosure

**Salt:** `matebench-round-1-1a285f14b38008d96e63c2c13b3a76bc631ee507dc0cc4248f84981d27ac3ba9`

Published with this commit: `corpora/generated.epd` (the pool),
`corpora/generated.meta.json` (the generator's seed and parameters), and the
twelve run logs in `logs/`. The checkpoint state is not published; every result
in it is in the logs.

## Checking the commitment

Each of these must print the hash in `OPEN.md`:

    python -c "import hashlib; print(hashlib.sha256(b'matebench-round-1-1a285f14b38008d96e63c2c13b3a76bc631ee507dc0cc4248f84981d27ac3ba9').hexdigest())"
    python -c "import hashlib; print(hashlib.sha256(open('corpora/generated.epd','rb').read()).hexdigest())"
    python -c "import hashlib; b=open('corpora/generated.meta.json','rb').read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'); print(hashlib.sha256(b).hexdigest())"

The metadata was written with Windows line endings when its hash was committed,
and the repository stores text with LF, so the last command restores CRLF before
hashing; the content is otherwise byte for byte the committed file. Hashed as
stored, with LF, it is
`1af7666439776f238e0be677c975a0740a02b44f6b7be92d1edc12b7cad5a54b`. The pool
was written with LF from the start and needs no such step.

The split, and any run, can then be reproduced:

    python bench/heldout.py corpora/generated.epd --salt matebench-round-1-1a285f14b38008d96e63c2c13b3a76bc631ee507dc0cc4248f84981d27ac3ba9 --fraction 0.2 --out-dir round-1-split
    python bench/matebench.py submit manifests/matehunter-19.json --against manifests/stockfish-19.json manifests/huntsman-1.json --positions round-1-split/generated.heldout.epd --min-depth 1 --nodes 10000000

The pool itself can be regenerated from `generated.meta.json` with
`bench/generate_corpus.py`, given MateProver 0.2.0 and the matetrack and ChestUCI
files whose hashes the metadata records.

## Results

Finding track, verified claims, one thread, verification by MateProver 0.2.0 at
1,000,000 nodes. No claim by any engine was refuted. Each cell pairs the first
engine named against the second: positions only the first verified, positions
only the second verified, and the two-sided sign test on those.

### Held-out set: 972 positions (960 at d1-7, 12 at d8-12)

| budget | MateHunter 19 | Stockfish 19 | Huntsman 1 | MateHunter vs Stockfish | MateHunter vs Huntsman | Huntsman vs Stockfish |
|---|---:|---:|---:|---|---|---|
| 10,000,000 | 963 | 963 | 971 | +5/-5, p = 1.0 | +0/-8, p = 0.0078 | +8/-0, p = 0.0078 |
| 100,000 | 815 | 872 | 914 | +14/-71, p < 0.0001 | +6/-105, p < 0.0001 | +55/-13, p < 0.0001 |
| 10,000 | 642 | 767 | 801 | +3/-128, p < 0.0001 | +2/-161, p < 0.0001 | +60/-26, p = 0.0003 |

At d8-12 (12 positions): at 10,000,000 nodes MateHunter against Stockfish is
+3/-1 (p = 0.63), MateHunter against Huntsman +0/-3 (p = 0.25), and Huntsman
against Stockfish +5/-0 (p = 0.06). One claim per engine was unconfirmed at
10,000,000 nodes.

### Development split: 3,962 positions (3,930 at d1-7, 32 at d8-12)

| budget | MateHunter 19 | Stockfish 19 | Huntsman 1 | MateHunter vs Stockfish | MateHunter vs Huntsman | Huntsman vs Stockfish |
|---|---:|---:|---:|---|---|---|
| 10,000,000 | 3,935 | 3,938 | 3,956 | +12/-15, p = 0.70 | +3/-24, p < 0.0001 | +20/-2, p = 0.0001 |
| 100,000 | 3,320 | 3,570 | 3,727 | +57/-307, p < 0.0001 | +29/-436, p < 0.0001 | +217/-60, p < 0.0001 |
| 10,000 | 2,619 | 3,118 | 3,269 | +25/-524, p < 0.0001 | +10/-660, p < 0.0001 | +237/-86, p < 0.0001 |

At d8-12 (32 positions): at 10,000,000 nodes MateHunter against Stockfish is
+2/-2 (p = 1.0), MateHunter against Huntsman +0/-4 (p = 0.13), and Huntsman
against Stockfish +4/-0 (p = 0.13). Three claims per engine were unconfirmed at
10,000,000 nodes.

## What the round shows

The held-out set and the development split agree at every budget.

1. **On positions no engine could have been tuned on, MateHunter 19 shows no
   advantage over stock Stockfish 19.** At the reference budget the two are
   level (+5/-5 held out, +12/-15 in development). At 100,000 and 10,000 nodes
   MateHunter is behind, on both sets, at p < 0.0001. On ChestUCI, which is
   in-sample for MateHunter, it was ahead by +279/-36 at d14+ and +478/-59 at
   d10-13.
2. **Huntsman 1 is ahead of both** at every budget on both sets, significantly
   over all bands in every comparison (p <= 0.0078). Within the d8-12 band alone
   the counts are too small for most comparisons to reach significance.
3. **No engine over-claimed.** Every claim was verified or, for a handful at the
   largest budget, unconfirmed within MateProver's budget; none was refuted.

## What it does not show

Why MateHunter's ChestUCI advantage is absent here. Three explanations remain,
and this round cannot separate them:

- **Tuning.** MateHunter was tuned on matetrack, which contains ChestUCI, and the
  gain did not survive positions outside it.
- **Depth.** This pool is shallow: 44 of its 4,934 positions are mate in 8 or
  more, and none deeper than 9. MateHunter's ChestUCI gain was measured at mate
  in 10 and beyond. At d8-12 here the counts are too small to say anything.
- **Kind of position.** The pool descends from random checkmates. The tablebase
  pilot (`results/reference/REFERENCE.md`) found that simple material reverses
  engine rankings, and these positions are simpler than composed problems, even
  with the material that uncaptures add.

A pool of unseen positions at mate in 10 and deeper would separate the first two
from the third. The generator's yield falls sharply past mate in 6: of about 900
candidates per level, 106 had exactly mate in 6, then 60 at 7, 25 at 8 and 3 at
9. So that pool needs either a much larger generator run or composed problems no
engine was tuned on.

## Protocol notes

- The pool, the salt and the metadata matched their commitments.
- Minimality and absence were not run: no entrant emits the certificates those
  tracks require.
- One party generated the pool, opened the round and ran the engines. The
  engines were fixed binaries identified by hash, so nothing was tuned during the
  round, and the pool, the salt and every log are published here, so the split
  and every result can be reproduced.
