# MateBench

A benchmark for chess mate-solving engines, forks and configurations - built so
that "my engine is better at mates" is a claim someone else can check.

Mate-solving results are easy to get wrong in ways that are hard to see later:
a claimed mate nobody checked, an engine left at a default that switches its mate
search off, two things changed in one comparison, a corpus the engine was tuned
on, a pooled total that hides opposite effects at different depths. Each of those
is a rule the harness enforces, so that a published number comes with the
configuration, the positions and the verification needed to re-run it.

## What is different about this benchmark

**Claims are verified, not counted.** On the finding tracks every mate a
submission reports is verified before it scores. Stockfish-derived mate solvers
report mates longer than the shortest one, or echo the bound they were asked
for, and a benchmark that counts claims rewards exactly that. A false claim
scores zero, and the submitter can re-run the checker themselves.

**The judge is not an opinion, and it is not a ceiling.** A claim is verified
by a machine-checkable proof certificate, checked from scratch by a checker that
shares no code with any engine. A submission can supply its own certificates,
from any prover; a claim without one is re-proved by MateProver. So a
submission cannot be "unlucky" against the verifier - it can only be wrong - and
an engine that finds mates beyond MateProver's reach can still prove them.

**Configuration is explicit.** Mate options decide results: Matefish ships
with its `ProofNumberSearch` off and looks weak at its defaults, and MateHunter's
two profiles swap places depending on the clock. A submission carries a settings
manifest; the harness sets every option it is given, refuses one the engine does
not advertise, and never trusts an engine default.

**Positions no engine has seen.** Public mate corpora overlap: 6,526 of
ChestUCI's 6,545 positions are also in matetrack, which engines are tuned on.
`bench/generate_corpus.py` generates positions that cannot have been seen, by
stepping back from random checkmates and proving each shortest mate, and held-out
rounds commit to their split with a salted hash before any engine runs.

**The budget matches the question.** A node budget compares search per node; a
clock compares what a user gets. They can disagree: MateHunter's recommended
profile searches 2.7 times as many nodes per second as Stockfish 19, is never
ahead of it at equal nodes, and is ahead from about 2 seconds a position.
Engines from different families are only ever compared under a clock.

**Paired, and reported as discordant pairs.** Every arm sees every position.
Totals are shown; the discordant pairs and a sign test are the result, per depth
band. A pooled total can be two opposite effects cancelling: on ChestUCI two of
the reference engines are close overall and separate in opposite directions with
depth (`results/reference/REFERENCE.md`).

## Tracks

See `TRACKS.md`. In one line each:

| track | question | who can enter |
|---|---|---|
| finding | mates within N, **verified** | any UCI engine |
| speed | time to a verified find, paired on shared positions | any UCI engine |
| minimality | the *shortest* mate, certified | provers only |
| absence | "no mate within N", certified | provers only |
| other goals | selfmate, stalemate, helpmate, helpstalemate, selfstalemate | provers only, today |
| variants | x-check, x-capture, x-escape | provers only, today |

Minimality, absence, other goals and variants have one entrant each so far.
They are listed so an entrant can aim at them.

## What it has found

On generated positions no engine was tuned on, up to mate in 11, with every claim
verified and none refuted (`results/reference/REFERENCE.md`, "Out of sample"):

| | at equal nodes | at equal time |
|---|---|---|
| **Huntsman 1** | leads both others from mate in 6 | leads both others at every clock from 500 ms to 10 s, p < 0.0001; +74/-6 against MateHunter at 5 s on mate in 10 and 11 |
| **MateHunter 19** against stock Stockfish 19 | never ahead, mate in 1 to 11 | behind below 2 s, ahead from 2 s on mate in 9 to 11 (+143/-92 at 2 s, +125/-60 at 5 s) |
| MateHunter's two profiles | - | king-danger evaluator better at 500 ms and 1 s; recommended profile better at 2 and 5 s |

On ChestUCI, which is in-sample for MateHunter, its margin over stock was far
larger (+478/-59 at mate in 10 to 13). Untested so far: mate in 12 and deeper, and
composed problems outside matetrack.

## Running it

    python bench/matebench.py --list
    python bench/matebench.py fetch chestuci --chest-dir <ChestUCI install>
    python bench/matebench.py verify-corpora
    python bench/matebench.py submit submission.json --against manifests/huntsman-1.json
    python bench/matebench.py certify claims.jsonl --positions round.heldout.epd
    python bench/matebench.py generate --seed <name>
    python bench/matebench.py lint my_measurement.py
    python bench/matebench.py paired --help
    python bench/matebench.py table

`submit` runs any UCI engine described by a manifest, paired against the
reference engines in `manifests/`; SUBMISSION.md says what the manifest holds
and what the runner checks.

Each command is a script in `bench/` or `corpora/` and can be run directly;
the entry point only finds it and passes the arguments through.

The offline tests need python-chess and a MateProver checkout for its proof
checker, and no engine:

    export MATEBENCH_MATEPROVER_REPO=/path/to/mateprover
    python bench/test_submit.py
    python bench/test_certify.py
    python bench/test_hook.py

CI runs them on every push (`.github/workflows/ci.yml`).

## Reference results

`results/reference/` holds the raw logs of every measurement the reference
numbers come from, dated, with the configuration that produced each. The
summary is in `results/reference/REFERENCE.md`. Read the caveats there before
quoting a number - several are stated as *not established*, and the document
says which.

## Layout

    README.md, TRACKS.md, SUBMISSION.md, CONTRIBUTING.md, CHANGELOG.md
    bench/          the harness
      matebench.py        the entry point; `--list` names every command
      submit.py           the submission runner: any UCI engine, under a manifest
      certificates.py     checks the mate certificates a submission supplies
      absence.py          checks minimality and absence certificates
      certify.py          scores tracks 3 and 4 on certificates
      generate_corpus.py  generates positions no engine has seen
      heldout.py          the salted development / held-out split
      test_*.py           offline tests
    manifests/      the reference engines, described as submissions
    engines/        build.sh and README.md: build the reference engines from
                    their public sources and check each against its manifest
    corpora/        provenance, checksums, the fetch script and the generated
                    corpora; no third-party positions are vendored
    submissions/    entered results, one directory each, and INDEX.md
    rounds/         held-out rounds: commitment, split, results, disclosure
    studies/        pre-registered studies, each a plan, results and logs:
                    depth/, profile/, clock/
    results/reference/  reference logs and REFERENCE.md, the summary of results
    docs/           the measurement protocol, the held-out design
                    (HELDOUT.md) and the certificate formats (CERTIFICATES.md)
    .github/        CI

## Requirements

Python 3.10+, `python-chess`, and the engines under test. `engines/build.sh`
builds the reference engines from source.
`bench/config.py` reads the paths from environment variables - nothing in the
harness assumes a particular machine.

**The verifier is MateProver, and which build answered is part of every
result.** Numbers in this repository were verified with **MateProver v0.2.0**
(MIT, https://github.com/ScottMoore0/mateprover), or, in logs dated before
2026-09-13, with v0.1.0, whose search and checker 0.2.0 leaves unchanged. v0.3.0
adds absence and minimality certificates and changes neither, so use it: clone it
and build with CMake, or take a release binary, then point the harness at the
checkout and the binary:

    git clone --branch v0.3.0 https://github.com/ScottMoore0/mateprover
    export MATEBENCH_MATEPROVER_REPO=/path/to/mateprover
    export MATEBENCH_MATEPROVER=/path/to/mateprover-binary

A submission verified with a different build must say so, because the
verification budget and the certificate format are properties of that build
rather than of this harness.

## Status

Version 0.1.0; see `CHANGELOG.md`. The harness, the reference results, held-out
round 1 and three pre-registered studies are in the repository, with their logs.
Not yet public. The reference engines can be rebuilt from public sources
(`engines/`), node-budget results reproduce exactly on a rebuild, and
`CONTRIBUTING.md` states how a result is entered and what the maintainer checks.

**The maintainer of this repository is also a submitter**, which a held-out round
is not meant to allow. Until that changes, a round derives its salt from a part
committed by every party, so no party can steer the split alone
(`CONTRIBUTING.md`, section 7); everything else rests on the published plans,
hashes and logs, which anyone can re-run.

## Licence

MIT, for the harness and documents. Corpora are not included; each has its own
terms, recorded in `corpora/PROVENANCE.md`. The engines are their own projects
under their own licences.
