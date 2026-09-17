# Reference engines: building them yourself

The reference numbers in this repository were measured with binaries built on
one machine, and the manifests in `manifests/` record those binaries' sha256.
Nobody else can produce the same file: the hash depends on the compiler, its
version and the target architecture. What can be reproduced is the search, and
that is what a comparison needs.

## Build

    engines/build.sh [OUT_DIR] [ARCH]

builds all three from their public sources into `OUT_DIR` (default
`~/mate-engines/bin`, where the harness looks) for `ARCH` (default
`x86-64-avx2`), then runs UCI `bench` on each under each manifest's options and
stops unless every node count matches. It needs git, make, a C++ compiler,
python3, curl and network access.

| engine | source | patch | network | bench, under the manifest's options |
|---|---|---|---|---|
| Stockfish 19 | [official-stockfish/Stockfish](https://github.com/official-stockfish/Stockfish), tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d` | none | `nn-1a298aa575a0.nnue` | 2,497,913 |
| MateHunter 19, recommended profile | the same | [`matehunter.patch`](https://github.com/ScottMoore0/matehunter/blob/v0.1.0/matehunter.patch) from MateHunter v0.1.0, sha256 `d14cb5c22a513c8eb98c2323b3c0c7b35f92a670d86e8a6036c840c7ef8a821a` | `nn-1a298aa575a0.nnue` | 5,314,178 |
| MateHunter 19, king-danger evaluator | the same binary | | | 5,754,190 |
| Huntsman 1 | [joergoster/Stockfish-old](https://github.com/joergoster/Stockfish-old), tag `h1`, commit `136b800533e57fe7e646a53f7d1f726b635e5cc9` | none | `nn-6877cd24400e.nnue`, unused with `Use NNUE=false` | 7,468,942 |

Each manifest carries the same facts in its `bench` and `build` fields.

## Run

Point `MATEBENCH_ENGINES` at the output directory and submit as usual. The
runner hashes each binary; when the hash differs from the manifest's, it runs
`bench` under the manifest's options and accepts the binary only if the node
count matches, logging it as `a rebuild: sha256 differs from the manifest's …,
bench … matches`. A binary with a different search is refused.

## Why bench is enough, and what was checked

`bench` searches a fixed set of positions to a fixed depth with one thread and a
fixed hash size, and its node count changes with any change to the search, the
evaluation, the network or the options that reach either. It does not change with
the compiler or the SIMD target: Stockfish checks exactly that equality across
architectures in its own CI. On 2026-09-17, on the machine the reference numbers
came from:

| measured binary | rebuilt from public sources | bench, both | node-budget searches identical |
|---|---|---|---|
| Stockfish 19: g++ 13.3.0, `x86-64-avx512icl` | `x86-64-avx2`, and again `x86-64-bmi2` | 2,497,913 | 120 of 120 |
| MateHunter 19, recommended: a development build, g++ 13.3.0, `x86-64-avx512icl` | Stockfish 19 plus the public patch, `x86-64-avx2`, and again `x86-64-bmi2` | 5,314,178 | 120 of 120 |
| MateHunter 19, king-danger | the same | 5,754,190 | 120 of 120 |
| Huntsman 1: g++, architecture not recorded | `x86-64-avx2`, and again `x86-64-bmi2` | 7,468,942 | 120 of 120 |

"Identical" means the same final score, node count and best move for every one of
120 positions from `corpora/generated-deeper.epd` at `go mate N nodes 1000000`.
The source of the MateHunter development build was also compared file by file:
the Stockfish 19 base matches all 76 files of the `sf_19` source tree, and the
base plus the public patch equals the source the release was built from.

A full runner check agrees: `bench/submit.py` on 60 positions at mate in 9 to 11,
1,000,000 nodes, all four manifests, gave the same claims, verifications and
discordant pairs with the `x86-64-bmi2` rebuilds as with the measured binaries.

## What this does not cover

- **Node budgets reproduce; clocks do not.** A result under `--movetime` depends
  on the machine's speed and load, so a clock comparison has to be re-run on your
  own hardware, with every arm on it.
- **Threads.** The reference measurements use one thread. A multi-threaded search
  is not deterministic, on any build.
- **Matefish and Chest 3.19** appear in `results/reference/` but have no manifest
  and are not part of this recipe.
