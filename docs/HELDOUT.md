# The rotating held-out set

## Why

Any public corpus will be tuned on, and the public mate corpora are not
independent of each other: 6,526 of ChestUCI's 6,545 positions are also in
matetrack, so an engine tuned on matetrack is in-sample on ChestUCI as well.
A corpus is held out only if nobody could have tuned on its positions, whatever
the file is called, and only a check position by position shows that. The public
corpora are for development; a leaderboard position must come from positions the
submitter did not see.

## Mechanism

A round has a **salt**: a secret string chosen by the round's maintainer, or,
in a round with several parties, derived from one part committed by each of them
(`CONTRIBUTING.md`, section 7, and `bench/heldout.py --salt-parts`).

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
  is `bench/generate_corpus.py`, so a round can grow the pool with positions
  that have never existed before. It is disjoint from matetrack and ChestUCI by
  construction. Its limits are stated in `corpora/PROVENANCE.md`: only
  positions MateProver proves are kept, they descend from random checkmates,
  and the pool is shallow.
- **ChestUCI, supplied by whoever runs or checks the round, never by this
  repository.** Its authors' permission is needed to redistribute it, so nothing
  here ships it. The maintainer runs the round from their own copy of the
  `ChestUCI.epd` that ships with ChestUCI 5.2, rebuilt with
  `fetch_corpora.py chestuci` and checked against `CHECKSUMS.json`; anyone
  checking the round afterwards does the same with theirs. Results name its
  positions by id (`heldout.py --ids`: the first 16 hex digits of the sha256 of
  the position), never by FEN, so publishing a round's results does not publish
  the positions. Where to find the file, and which look-alikes do not match, is
  in `corpora/PROVENANCE.md`. ChestUCI is almost entirely contained in
  matetrack, so for any engine tuned on matetrack `tuned_on` removes nearly all
  of it; a round that includes such an engine cannot draw on ChestUCI.
- **Not matetrack** for any engine that was tuned on it. The manifest's
  `tuned_on` field declares tuning corpora, and `bench/submit.py` drops every
  position of a declared corpus for every arm in the run, so the arms still see
  identical positions. The exclusion is by position, not by file name, so it
  also removes a declared corpus's positions from any other corpus that
  contains them.
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
certificates. Never, during a round, the held-out positions - and for a corpus
that may not be redistributed, never at all: results identify those positions
by id, which anyone holding the corpus can map back to a position.

## What is not solved by this

A submitter who tunes on the whole public pool has tuned on the held-out
positions too, because they are drawn from it. The salted split defeats
*targeting* the held-out set; it does not defeat *overfitting the pool*. That
is what the generated corpus is for: a round can be seeded with fresh
positions that exist nowhere else until the round closes.
