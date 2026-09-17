# Submitting an engine or a configuration

This page is the manifest and the runner. `CONTRIBUTING.md` is the process:
what to send, what the maintainer checks, and how a result is published.

A submission is a UCI engine plus a **manifest**, and `bench/submit.py` runs it:

    python bench/matebench.py submit submission.json --against manifests/matehunter-19.json manifests/huntsman-1.json

The runner will not start without a manifest, because the single most common
measurement error found while building this benchmark was an engine evaluated
with its mate machinery left at a default that switches it off. The reference
engines are described by manifests too, in `manifests/`.

## The manifest

`submission.json`:

```json
{
  "name": "MyEngine 2",
  "binary": "myengine",
  "sha256": "…",
  "source": "https://…  (commit or release tag)",
  "licence": "GPL-3.0",
  "base": "Stockfish 19",
  "family": "stockfish",
  "uci_options": {
    "Threads": 1,
    "Hash": 256,
    "MateSolver": "true"
  },
  "tracks": ["finding", "speed"],
  "claims": "within-N",
  "tuned_on": ["matetrack.epd"],
  "certificates": {"channel": "info-string"},
  "notes": "MateSolver defaults off.",
  "bench": 4812345,
  "build": {"source": "https://…", "commit": "…", "make": "cd src && make -j build ARCH=<arch>"}
}
```

- `binary` - a file name in the engine directory (`MATEBENCH_ENGINES`), or an
  absolute path.
- `sha256` - of that binary. Results are keyed by the hash of the binary that
  ran. `submit submission.json --print-sha256` prints it.
- `bench` - optional: the node count UCI `bench` reports after the manifest's
  options are set. With it, a binary whose sha256 differs is accepted when its
  bench matches, as a rebuild of the same search with another compiler or
  architecture, and the log says so; without it, or with a different count, a
  hash mismatch refuses the run. Give it if your engine's `bench` is
  deterministic, so others can rebuild your submission and reproduce node-budget
  results.
- `build` - optional: how to build the binary from source, for a reader.
  `engines/README.md` shows the reference engines'.
- `base` and `family` - the family decides the budget. Arms in one family are
  compared under a node limit; a run with arms from more than one family is
  refused unless it uses `--movetime` (see TRACKS.md, Budgets). Without
  `family`, it is the first word of `base`; a base of `own` is a family of one.
- `uci_options` - **every** option that affects mate search, including the ones
  whose default is already what you want. The runner sets exactly this list. The
  engine must advertise every name in it: an engine accepts a `setoption` for a
  name it does not know and ignores it, so an option it does not advertise
  refuses the run instead of silently running at a default. Options the engine
  advertises that the manifest leaves out are listed in the log with the
  defaults that applied.
- `tracks` - `bench/submit.py` scores `finding` and `speed`. Minimality and
  absence need a prover's certified answer and are run by `vs-prover`.
- `claims` - `within-N` (the engine reports *a* mate within the bound) or
  `shortest` (the engine asserts minimality). This runner scores both as
  `within-N`. An engine that echoes the bound it was given is `within-N`
  whatever its output looks like.
- `tuned_on` - the corpora the engine was tuned or developed on, as file names
  in the corpora directory. Every position in them is dropped for every arm in
  the run, so the arms still see the same positions and none is scored on its
  own training data. A declared corpus has to be present, or the run is refused.
- `certificates` - how the engine supplies proofs of its own claims, if it does
  (see below). `"none"` if it does not.
- `notes` - anything a reader of the log needs, in plain words.

## Certificates

A claim counts only once it is verified. Without certificates, MateProver
re-proves it at the claimed length within the verification budget, and a claim
it cannot re-prove in time is reported as **unconfirmed**. That caps a
submission at MateProver's reach: an engine that finds mates MateProver cannot
prove would get no credit for them.

A certificate removes the cap. It is a complete proof tree in MateProver's
certificate format, version 1, specified in `docs/PROOF_FORMAT.md` of the
MateProver repository closely enough to produce one without reading MateProver.
At every attacker node it gives the move; at every defender node it lists every
legal reply, each with a sub-proof; every line ends in checkmate.

It can be supplied in two ways:

- `{"channel": "info-string"}` - the engine prints `info string proof <json>`
  during the search, before `bestmove`. The last one printed is taken.
- `{"channel": "command", "argv": [...], "timeout": 600}` - after a claim, the
  runner starts this command, replacing `{fen}`, `{dm}` and `{engines}` in its
  arguments and giving `<fen> bm #<dm>;` on stdin. The certificate is read from
  its output, either as a `proof <json>` token as MateProver prints it, or as a
  line that is a JSON object. Any prover can be used; for example, MateProver
  itself with a larger node budget than the verification budget:

      ["{engines}/mateprover", "--emit-proof", "--direct-depth", "--no-portfolio",
       "--node-limit", "20000000", "-z", "{dm}", "-"]

Every certificate is checked by `tools/verify_proof.py` from the MateProver
checkout named by `MATEBENCH_MATEPROVER_REPO`, a separate program that
re-derives every legal move with python-chess and shares no code with any
engine. It starts from the corpus position, never from anything the submission
sends, and accepts the certificate only if every move is legal, every leaf is
checkmate, every defender node lists exactly the legal replies, and the
certificate's depth equals the claimed mate distance. The log names the
checker by path and sha256. Certificates over `--max-certificate-mb` (256 MB by
default) are rejected unread.

A verified certificate verifies the claim. A claim with no certificate, or with
one that fails, is re-proved by MateProver as usual, and the log lists every
rejected certificate with the checker's reason. A certificate proves a mate
within its depth; it does not prove that no shorter mate exists, so it never
scores on minimality.

## What the runner does

1. Loads every manifest and refuses one with a missing or malformed field.
2. Hashes each binary. A mismatch is refused unless the manifest records a
   `bench` node count and the binary reproduces it under the manifest's options.
3. Starts each engine, reads its option list, and refuses a manifest option the
   engine does not advertise.
4. Refuses a node budget across families.
5. Draws the positions: the `bm #N` lines of `--corpus` (or of `--positions`,
   such as a held-out split from `heldout.py`) within `--min-depth` and
   `--max-depth`, minus every `tuned_on` corpus, then `--n` of them under
   `--seed` if given. Every arm gets the same positions.
6. Runs a positive control: each arm must find a mate in one under its own
   manifest. An engine that reads EOF, or runs with its search off, answers
   instantly and would otherwise score as a hard position, not a broken run.
7. Runs every arm on every position, each search in a fresh process over a live
   pipe (never with stdin redirected from a file), sending the manifest's
   options and `go mate N` under the budget.
8. Accepts a mate score only if `0 < dm <= N`, and takes the shortest reported.
9. Checks each claim's certificate, if the arm supplies them.
10. Re-proves every other claim with MateProver (`--direct-depth --no-portfolio`
    at the claimed length, `--verify-nodes`, 1,000,000 by default): verified,
    refuted, unconfirmed or error, never merged.
11. Reports, and checkpoints everything under a key that includes the binary's
    hash, the options, the budget and the certificate checker, so a changed
    engine, setting, budget or checker never replays an old result.

## What you get back

A dated log (by default in the results directory, `submit_<name>_<date>.log`)
with:

- the positions, their source and its checksum, the band profile, and how many
  positions each `tuned_on` corpus removed;
- the budget, the MateProver build that re-proved claims, and the certificate
  checker's path and sha256;
- for every arm, the engine's own name, its hash, family, source and licence,
  the options set, and the options left at their defaults;
- per arm: claims, verified (split into by certificate and by MateProver),
  refuted, unconfirmed, errors, rejected certificates, and searches that did not
  end normally;
- refuted claims, rejected certificates with the checker's reason, claims with
  no certificate and why, and anything the engine printed on an unsolved
  position beyond what it prints on a solved one;
- per band, verified positions for every arm, and for the submission against
  each reference: the discordant pairs and a two-sided sign test, with reported
  claims for context;
- speed, on the positions both arms verified: which was faster on how many,
  the sign test, and the median and mean time ratio.

`--keep-certificates DIR` also writes every certificate the submission supplied,
so anyone can re-run the checker on them.

## Engines that run somewhere else

For engines that run under WSL or in a container, set `MATEBENCH_LAUNCHER` to the
command that starts them (for example `wsl -e`, or a JSON list of arguments) and
`MATEBENCH_ENGINES_EXEC` to the engine directory as the launcher sees it.
Binaries are still hashed through `MATEBENCH_ENGINES`. `MATEBENCH_MATEPROVER`
points at a MateProver binary to run directly instead. `bench/config.py`
describes all of them.

## Before you submit

Run `python bench/lint_measurement.py` over any script you changed. It blocks
five errors that have produced wrong numbers in this project's own measurements:
no distance check on a mate score, wall-clock where a node budget exists, arms
aggregated over different position sets, verdict strings with no "not
established" branch, and a Stockfish-fork arm with `MateMode=true`. Each rule
cites the case it came from; `docs/measurement-protocol.md` has them in full.

If you change `bench/submit.py` or `bench/certificates.py`, run
`python bench/test_submit.py`: it runs the runner against scripted engines that
lie, crash, forge certificates and fail the positive control, with MateProver's
real checker, and needs no real engine.

## What will not be accepted as a result

- A solve count that was not verified.
- A certificate that did not pass the checker, counted as a verification.
- A comparison against a reference run at settings other than its manifest.
- A pooled total without its bands.
- A result on positions an arm was tuned on.
- A speed figure measured on a loaded machine, or with a timeout in the ratio.
- "Better than Chest" without saying which Chest and how it was configured -
  the reference Chest is 3.19 (1999-era), driven as `WinChest.exe` with its
  endgame databases off, and the reference results say so.
