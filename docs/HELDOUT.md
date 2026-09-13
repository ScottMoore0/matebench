# The rotating held-out set

## Why

Any public corpus will be tuned on, and the reference results show exactly
what that does. On matetrack, which MateHunter was tuned on, MateHunter and
Huntsman were "indistinguishable" for a week. On ChestUCI, which neither had
seen, they separate by depth in opposite directions at p = 0.001 and
p = 0.0005. The public corpora are for development. A leaderboard position
must come from positions the submitter did not see.

## Mechanism

A round has a **salt**: a secret string chosen by the round's maintainer.

1. **Open.** The maintainer publishes `sha256(salt)` and the checksums of the
   round's source corpora (`corpora/CHECKSUMS.json`). Submitters see the
   commitment, not the salt.
2. **Split.** `bench/heldout.py <corpus> --salt <salt>` assigns each position
   to held-out or development by `sha256(salt | position)`: a fixed fraction
   (default 20%) is held out. The split depends on the salt and the position
   and nothing else, so it cannot be steered and can be reproduced later.
3. **Run.** Every submission and every reference engine runs on the held-out
   set under the track rules in TRACKS.md. Per-band counts of the held-out set
   are printed at split time and recorded before any engine runs.
4. **Close.** The maintainer publishes the salt. Anyone can now check that
   `sha256(salt)` matches the opening commitment and regenerate the exact
   held-out set from the checksummed corpus, and re-run any result.
5. **Rotate.** The next round uses a new salt. Positions from a closed round's
   held-out set are public and go back to development.

## What goes in the pool

- **The generated corpus** first: its terms permit anything and its generator
  is in the MateProver repository, so a round can grow the pool with positions
  that have never existed before.
- **ChestUCI** only with the authors' permission for the positions to be
  redistributed as a held-out set; without it the round can still use the set,
  but only reporting results, not the positions.
- **Not matetrack** for any engine that was tuned on it. The manifest's
  `notes` field is where a submitter declares tuning corpora, and a declared
  corpus is excluded from that submission's held-out pool by position hash.
- **Not tablebase positions**, whatever their terms. Exact depths come free from
  a DTM tablebase, but a pilot on 3-4 man Gaviota positions
  (`results/reference/dtm_pilot_2026-09-13.log`) reversed the ranking of every
  engine measured: MateProver 71% to 37%, Stockfish 19 44% to 60%, against
  ChestUCI positions of the same depths. A pool containing them would measure
  endgame technique, not problem solving. They belong, if anywhere, in a separate
  track reported under its own name.

## What a submitter sees

Before the round: the commitment, the corpus checksums, the band profile of
the held-out set, and the track budgets. After the round: the salt, their
per-band results paired against every reference engine, and their
certificates. Never, during a round, the held-out positions.

## What is not solved by this

A submitter who tunes on the whole public pool has tuned on the held-out
positions too, because they are drawn from it. The salted split defeats
*targeting* the held-out set; it does not defeat *overfitting the pool*. That
is what the generated corpus is for: a round can be seeded with fresh
positions that exist nowhere else until the round closes.
