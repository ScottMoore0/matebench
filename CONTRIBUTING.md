# Entering a result

A result enters MateBench as a pull request that adds one directory under
`submissions/`. This page is the whole process: what to send, what happens to
it, and what would make it fail. `SUBMISSION.md` describes the manifest and the
runner; `TRACKS.md` what each track scores.

## The short version

1. Write a manifest for your engine (`SUBMISSION.md`), including `bench` and
   `build` so anyone can rebuild it.
2. Run `bench/submit.py` against the reference manifests on a committed corpus.
3. Open a pull request adding `submissions/<engine>-<version>/` with the
   manifest, the run logs, a `RUN.md`, and any certificates.
4. The maintainer rebuilds your engine from your recipe, re-runs the node-budget
   comparison, and merges the result with what reproduced and what did not.

## 1. What counts as a result

- **Verified claims only.** A mate scores when a certificate you supplied checks,
  or when MateProver re-proves it. An unverified count is not a result.
- **Paired.** Your engine and every reference engine see the same positions.
  `bench/submit.py` does this for you; a comparison against numbers from another
  run, another machine or another corpus is not a result.
- **Under one budget.** Node budgets within a family, a clock across families.
- **Reported as discordant pairs per band.** The runner does this; a pooled total
  on its own is not a result.

## 2. Prepare

- **The engine.** Any UCI engine. Give `sha256`, and give `bench` (the node count
  UCI `bench` reports under your manifest's options) and `build` (source, commit,
  patch if any, make line) so that anyone can rebuild it and the runner can
  accept the rebuild. An engine nobody can obtain or rebuild can still be run,
  but its result is labelled as unreproducible.
- **The options.** Every option that affects mate search, set explicitly,
  including ones already at their default. The runner refuses an option your
  engine does not advertise.
- **The corpus.** One with a checksum in `corpora/CHECKSUMS.json`. The generated
  corpora are committed here; matetrack and ChestUCI are fetched per user.
  Declare in `tuned_on` every corpus your engine was developed on: its positions
  are dropped for every arm, so nobody is scored on their own training data.
- **The budget.** The reference budgets are 10,000,000, 100,000 and 10,000 nodes,
  and clocks of 0.5, 1, 2, 5 and 10 seconds. A result at some other budget is
  accepted; a result at only one budget is accepted, and says less.

## 3. Run

    python bench/matebench.py submit submissions/<engine>/manifest.json \
        --against manifests/stockfish-19.json manifests/huntsman-1.json \
        manifests/matehunter-19.json \
        --positions corpora/generated-deeper.epd --min-depth 9 --max-depth 11 \
        --nodes 10000000 --log submissions/<engine>/nodes-10M.log

Use `--movetime` instead of `--nodes` for a clock, on an otherwise idle machine,
and say how many searches ran at once. Repeat per budget. Keep every log.

## 4. Open a pull request

Add `submissions/<engine>-<version>/`:

| file | what it holds |
|---|---|
| `manifest.json` | the manifest the runs used, unedited |
| `*.log` | every run log, unedited: they carry the corpus hash, the options, the verifier and the per-band result |
| `RUN.md` | machine (CPU, cores, OS), how many searches at once, MateProver version, the exact commands, and anything you want read alongside the numbers |
| `certificates/` | optional: the certificates your engine supplied, as `--keep-certificates` writes them |

Title the pull request `Result: <engine> <version>`. The template lists the
checks. Do not edit `results/reference/` or another submission.

## 5. What the maintainer does

1. Reads the manifest and refuses one that hides an option or names a corpus
   with no checksum.
2. Rebuilds your engine from `build`, and checks `bench` against the manifest.
3. Re-runs the node-budget comparison from the rebuilt binary. Node-budget
   results are deterministic for one thread, so they must match your logs
   exactly: same claims, same verifications, same discordant pairs.
4. Re-verifies a sample of your certificates with MateProver's checker.
5. Merges the pull request with a row in `submissions/INDEX.md` recording what
   reproduced, and what did not.

Anything that does not reproduce is published as such, with both logs, rather
than quietly dropped. A clock result is not re-run for equality, because it
cannot be: it is published with the machine it came from.

## 6. Re-running someone else's result

Every merged submission carries its manifest, its build recipe and its corpus
hash, so anyone can re-run it. A re-run that disagrees is itself a pull request:
add `submissions/<engine>-<version>/replications/<your-name>/` with your logs and
`RUN.md`. Disagreements are recorded next to the original.

## 7. Held-out rounds with more than one party

`docs/HELDOUT.md` describes a round with one salt: it is committed to as
`sha256(salt)` before the pool exists, it decides the split, and it is published
at the close. A round with several parties can split the salt between them, so
that no one chooses the split:

1. **Every party commits.** Each publishes `sha256(part)` of a secret string of
   its own, before the pool is generated.
2. **The salt is all the parts.** At split time,
   `bench/heldout.py <corpus> --salt-parts <part> <part> ...` derives the salt as
   sha256 of the parts joined by newlines, in the order `OPEN.md` lists them. Any
   party can check afterwards that its part was used.
3. **Everything is published at the close:** every part, the pool, the metadata,
   and every log, so the split can be reproduced and any run repeated.

## 8. What will not be accepted

- A solve count that was not verified, or a certificate that failed the checker
  and was counted anyway.
- A comparison against a reference engine at settings other than its manifest.
- Edited logs. Send what the runner wrote.
- A result whose engine cannot be rebuilt or obtained, presented as
  reproducible.
- Node-budget results that do not reproduce from a rebuild, presented without
  saying so.

## 9. Terms

The harness and the documents are MIT. A submission's text and logs enter under
the same licence. Corpora are not redistributed here, and engine binaries are not
hosted here: a submission names its source and its hash.
