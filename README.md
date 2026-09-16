# MateBench

A benchmark for chess mate-solving engines, forks and configurations - built so
that "my engine is better at mates" is a claim someone else can check.

It exists because a week of careful measurement on two engines produced more
retractions than results, and every retraction had the same shape: a comparison
that changed two things at once, an engine run with its mate machinery switched
off by default, a claimed mate that was never verified, a headline read off a
pooled total that hid two opposite effects. The harness here encodes each of
those lessons as a rule the tooling enforces, not a paragraph the reader is
asked to remember.

## What is different about this benchmark

**Claims are verified, not counted.** On the finding tracks every mate a
submission reports is verified before it scores. Every Stockfish-derived mate
solver measured so far over-claims - reporting a mate longer than the true one,
or simply echoing the bound it was asked for - and a benchmark that counts
claims rewards exactly that. A false claim here scores zero, and the submitter
can re-run the checker themselves.

**The judge is not an opinion, and it is not a ceiling.** A claim is verified
by a machine-checkable proof certificate, checked from scratch by a checker that
shares no code with any engine. A submission can supply its own certificates,
from any prover; a claim without one is re-proved by MateProver. So a
submission cannot be "unlucky" against the verifier - it can only be wrong - and
an engine that finds mates beyond MateProver's reach can still prove them.

**Configuration is explicit.** Two of the three reference engines ship with
their mate solver *off* by default (`ProofNumberSearch`, `MateMode`/`MateEval`).
A submission carries a settings manifest and the harness sets every toggle it
is given, never trusting an engine default. Measured at defaults, both of those
engines look weak; that is a measurement error, not a finding.

**Paired, and reported as discordant pairs.** Every arm sees every position.
Totals are shown; the discordant pairs and a sign test are the result. A pooled
total can be two opposite effects cancelling - the reference engines were
"indistinguishable" at n=30 for a week, and are in fact separated by depth in
opposite directions at n=400.

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

The last four tracks currently have one entrant. That is the point of listing
them.

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

## Reference results

`results/reference/` holds the raw logs of every measurement the reference
numbers come from, dated, with the configuration that produced each. The
summary is in `results/reference/REFERENCE.md`. Read the caveats there before
quoting a number - several are stated as *not established*, and the document
says which.

## Layout

    bench/          the harness: paired UCI comparison, verify-against-prover,
                    budget derivation, headroom gate, and the measurement lint
    bench/matebench.py   the entry point; `--list` names every command
    bench/submit.py      the submission runner: any UCI engine, under a manifest
    bench/certificates.py   checks certificates a submission supplies
    bench/test_submit.py    offline tests for the runner and the certificate check
    manifests/      the reference engines, described as submissions
    bench/absence.py     checks minimality and absence certificates
    bench/certify.py     scores tracks 3 and 4 on certificates
    bench/generate_corpus.py   generates positions no engine has seen
    docs/CERTIFICATES.md the minimality and absence certificate formats
    rounds/         held-out rounds: commitment, split, results, disclosure
    corpora/        provenance and fetch script; no third-party data vendored
    results/        reference logs and summary
    docs/           methodology: the measurement protocol and the held-out design
    docs/HELDOUT.md the rotating held-out set: salted split, commitment, rotation
    TRACKS.md       what is measured and how it is scored
    SUBMISSION.md   how to submit an engine or configuration

## Requirements

Python 3.10+, `python-chess`, `numpy`, and the engines under test.
`bench/config.py` reads the paths from environment variables - nothing in the
harness assumes a particular machine.

**The verifier is MateProver, and which build answered is part of every
result.** Numbers in `results/reference/` were verified with **MateProver
v0.2.0** (MIT), from https://github.com/ScottMoore0/mateprover, or, in logs dated
before 2026-09-13, with v0.1.0, whose search and checker 0.2.0 leaves unchanged.
Clone it and build with CMake, or take a release binary; then point the
harness at the checkout:

    git clone --branch v0.2.0 https://github.com/ScottMoore0/mateprover
    export MATEBENCH_MATEPROVER_REPO=/path/to/mateprover

A submission verified with a different build must say so, because the
verification budget and the certificate format are properties of that build
rather than of this harness.

## Status

Pre-release. The harness and reference numbers are real and were produced by
the scripts here. `bench/matebench.py` is the single entry point; `submit` runs a
submission end to end from its manifest; every fetch
records its corpus checksum in `corpora/CHECKSUMS.json`; `results/reference/TABLES.md`
is regenerated from the logs; the held-out design is in `docs/HELDOUT.md`.
Nothing here has been published.

## Licence

MIT, for the harness and documents. Corpora are not included; each has its own
terms, recorded in `corpora/PROVENANCE.md`. The engines are their own projects
under their own licences.
