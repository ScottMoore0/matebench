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

**Claims are verified, not counted.** On the finding tracks a submission's
reported mates are re-proved by an independent prover and only the
certificates score. Every Stockfish-derived mate solver measured so far
over-claims - reporting a mate longer than the true one, or simply echoing the
bound it was asked for - and a benchmark that counts claims rewards exactly
that. A false claim here scores zero, and the submitter can re-run the checker
themselves.

**The judge is not an opinion.** The verifier is MateProver, whose output is a
machine-checkable proof certificate re-derived from scratch by a checker
sharing no code with the engine. A submission cannot be "unlucky" against it;
it can only be wrong.

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

## Reference results

`results/reference/` holds the raw logs of every measurement the reference
numbers come from, dated, with the configuration that produced each. The
summary is in `results/reference/REFERENCE.md`. Read the caveats there before
quoting a number - several are stated as *not established*, and the document
says which.

## Layout

    bench/          the harness: paired UCI comparison, verify-against-prover,
                    budget derivation, headroom gate, and the measurement lint
    corpora/        provenance and fetch script; no third-party data vendored
    results/        reference logs and summary
    docs/           methodology and the engineering findings behind it
    TRACKS.md       what is measured and how it is scored
    SUBMISSION.md   how to submit an engine or configuration

## Requirements

Python 3.10+, `python-chess`, `numpy`; a MateProver binary for verification;
the engines under test. `bench/config.py` reads the paths from environment
variables - nothing in the harness assumes a particular machine.

## Status

Pre-release. The harness and reference numbers are real and were produced by
the scripts here; the packaging (a single CLI entry point, a corpus fetcher
with checksums, a results-table generator) is not finished. Nothing here has
been published.

## Licence

MIT, for the harness and documents. Corpora are not included; each has its own
terms, recorded in `corpora/PROVENANCE.md`. The engines are their own projects
under their own licences.
