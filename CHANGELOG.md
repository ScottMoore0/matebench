# Changelog

Versions follow [semantic versioning](https://semver.org). The interfaces are the
submission manifest (`SUBMISSION.md`), the certificate formats
(`docs/CERTIFICATES.md`) and the claims file `certify` reads. Fields may be added
to any of them without a major bump; the meaning of an existing field will not
change without one.

A result is not an interface. Reference numbers change when a measurement is
repeated or corrected, and each change is recorded in `results/reference/REFERENCE.md`
with its reason.

## Unreleased

- **The reference engines can be rebuilt from public sources.** `engines/build.sh`
  builds Stockfish 19, MateHunter 19 and Huntsman 1 at pinned commits, with
  MateHunter's public patch, and checks each against its manifest's `bench` node
  count. `engines/README.md` records the check: rebuilt for other architectures,
  every engine gave the same bench and identical node-budget searches, 120 of 120.
- **Manifests may record `bench` and `build`.** The runner accepts a binary whose
  sha256 differs from the manifest's when its bench matches, and logs it as a
  rebuild; before, any hash mismatch refused the run.

## 0.1.0 - 2026-09-17

**First version.**

- **Submission runner.** `bench/submit.py` runs any UCI engine described by a
  manifest: the binary is checked by sha256, every option in the manifest must be
  advertised by the engine and is set explicitly, a known mate in one is a
  positive control, and results are paired against the reference engines, per
  depth band, as discordant pairs with a two-sided sign test. Engines from
  different families are compared only under a clock.
- **Verification.** Every mate a submission reports is verified before it scores:
  by a certificate the submitter supplies, checked by MateProver's independent
  checker, or by re-proof with MateProver.
- **Certificates for minimality and absence.** The `matebench-absence-1` and
  `matebench-minimality-1` formats (`docs/CERTIFICATES.md`), a checker
  (`bench/absence.py`) and scoring for tracks 3 and 4 (`bench/certify.py`).
  MateProver 0.3.0 emits both.
- **Generated corpora.** `bench/generate_corpus.py` produces positions no engine
  can have seen, stepping back from random checkmates and proving each shortest
  mate, and rejects material no game can reach. Three corpora are committed, to
  mate in 11.
- **Held-out rounds.** A salted split committed by hash before any engine runs
  (`docs/HELDOUT.md`); round 1 is opened, run and closed in `rounds/round-1/`.
- **Reference results and studies.** `results/reference/REFERENCE.md` summarises
  every measurement, with logs. Three pre-registered studies in `studies/`
  measure MateHunter 19, Stockfish 19 and Huntsman 1 out of sample by depth, by
  profile and by clock.
- **Corrections recorded in this version.** ChestUCI is 99.7% contained in
  matetrack, so every MateHunter result on it is in-sample. An earlier minimality
  figure for MateProver measured nothing and is retracted.
- **CI** runs the offline tests against MateProver 0.3.0's proof checker.
