# Submitting an engine or a configuration

A submission is a UCI engine plus a **manifest**. The manifest is not optional
and the harness will not run without one, because the single most common
measurement error found while building this benchmark was an engine evaluated
with its mate machinery left at a default that switches it off.

## The manifest

`submission.json`:

```json
{
  "name": "MateHunter 18",
  "binary": "matehunter",
  "sha256": "…",
  "source": "https://…  (commit or release tag)",
  "licence": "GPL-3.0",
  "base": "Stockfish 18",
  "uci_options": {
    "Threads": 1,
    "Hash": 256,
    "MateEval": "true",
    "MateMode": "false"
  },
  "tracks": ["finding", "speed"],
  "claims": "within-N",
  "notes": "MateMode off: its pruning disables cost 21 of 234 positions at d26+."
}
```

- `uci_options` - **every** option that affects mate search, including the
  ones whose default is already what you want. The harness sets exactly this
  list and nothing else. If an option is missing, the engine's default applies,
  and the benchmark records that it did.
- `claims` - `within-N` (the engine reports *a* mate within the bound; scores on
  finding) or `shortest` (the engine asserts minimality; scores on minimality,
  and its certificates are checked). Say which. An engine that echoes the bound
  it was given is `within-N` whatever its output looks like.
- `sha256` - of the binary you ran. Results are keyed by it.

## What the harness does with it

1. Loads the corpus for the requested track and band.
2. Starts the engine over a live pipe (never with stdin redirected from a file:
   an engine at EOF answers instantly without searching and looks like a fast
   failure), sends the manifest's options, and asks `go mate N` under the
   track's budget.
3. Parses the mate score with the sign check `0 < dm <= N`.
4. Re-proves every accepted claim with MateProver and keeps the certificate.
5. Runs the reference engines on the same positions under their own manifests,
   and reports paired.

## What you get back

A dated log in the format of `results/reference/*.log`: per-band counts for
your engine and each reference, discordant pairs, sign tests, verification
counts (verified / unconfirmed / rejected), and - on the speed track - the
paired time ratios. Plus the certificates, so you can re-run
`tools/verify_proof.py` from the MateProver repository yourself.

## Before you submit

Run `python bench/lint_measurement.py` over any script you changed. It blocks
on the errors that produced wrong published numbers here: no distance check on
a mate score, wall-clock where a node budget exists, arms aggregated over
different position sets, verdict strings with no "not established" branch, a
Stockfish-fork arm with `MateMode=true`. Each rule cites the retraction it came
from.

## What will not be accepted as a result

- A solve count that was not verified.
- A comparison against a reference run at settings other than its manifest.
- A pooled total without its bands.
- A speed figure measured on a loaded machine, or with a timeout in the ratio.
- "Better than Chest" without saying which Chest and how it was configured -
  the reference Chest is 3.19 (1999-era), driven as `WinChest.exe` with its
  endgame databases off, and the reference results say so.
