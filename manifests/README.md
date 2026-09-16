# Reference manifests

The reference engines as `bench/submit.py` runs them, at the configurations
`results/reference/REFERENCE.md` records. Pass any of them to `--against`:

    python bench/matebench.py submit submission.json --against manifests/matehunter-19.json manifests/huntsman-1.json

Each `sha256` is the binary the reference results were measured with. A run
refuses a binary whose hash differs, so to run these against your own builds,
copy the manifest, build or download the engine, and put your hash in the copy
(`submit <manifest> --print-sha256` prints it). Results are keyed by the hash,
so a rebuilt engine is a different arm, as it should be.

| manifest | engine | where a third party gets it |
|---|---|---|
| `matehunter-19.json` | MateHunter 19, recommended profile | https://github.com/ScottMoore0/matehunter, tag v0.1.0; this hash is the development build whose search the release reproduces |
| `stockfish-19.json` | Stockfish 19 | https://stockfishchess.org, release 19; this hash is a build from the release source with MateHunter's compiler and flags |
| `huntsman-1.json` | Huntsman 1 | https://github.com/joergoster/Stockfish-old/releases/tag/h1 |

MateProver is not here: it is not a UCI engine, it is the verifier, and its
cross-family comparisons run through `vs-prover`.
