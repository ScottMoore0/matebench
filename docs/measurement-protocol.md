---
name: mate-engine-measurement-protocol
description: "Measurement rules for the mate-engine work, each learned from a wrong conclusion that survived until it was applied"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0398cdff-fc0b-4843-96f6-dbca8cda7289
  modified: 2026-08-23T15:58:13.794Z
---

Rules for benchmarking the mate engines. Each one exists because a conclusion
was reported and later overturned.

**Replicate in a DIFFERENT band, not just on fresh positions in the same one.**
Fresh d20 positions confirmed hunt18k > Huntsman twice; adjacent bands reversed
it. Same-band replication tests sampling noise only, never generality.

**Verdict logic must test the thing you care about.** A `gate0.py` check of
`union > best_single` printed "portfolio worth building" on a gain contributed
entirely by two alpha-beta engines while DFPN contributed 0. A `final_ab.py`
check of `delta >= 0` reported "pays" for a null result. Test the specific
quantity, and never let zero read as a pass.

**NEVER TRUST YOUR OWN VERDICT LINE.** Five have now overstated their data:
`union > best_single` said "portfolio worth building" when DFPN contributed 0;
`delta >= 0` said "pays" for a null result; `only_dfpn > 0` said "earns its
place" for 2 in 100; a static hint said "SearchDepth is the cause" regardless of
the numbers; and `max()` over tied values said "PEAK IN THE MIDDLE" of a
plateau. Print the table, read the table, and let the verdict line be a
reminder of the test - not the finding.

**Node counts are only comparable under a NODE budget.** Under a time limit the
faster binary searches further, so identical counts are impossible and differing
counts prove nothing.

**Verify a flag changes the search before measuring it** - but do not leap to
"the option is unrecognised". Four Chest options returned byte-identical node
counts, which looked like unknown names being ignored. All six were REAL and
advertised; they were no-ops because each already defaulted to the value being
set. The identical counts had a third cause entirely (the engine was aborting on
a stale scratch file and never searching at all). Read the option list off the
engine, and check its defaults, before forming a hypothesis about it.

**Profile before claiming a hotspot.** "Per-node allocation is the clearest win"
came from seeing `gen_pseudo<std::vector<Move>>` rank high - that is generation,
not allocation. Allocation was 3.9%. The real costs were the TT (~21.6%) and a
locale-aware `tolower` at 5.4%.

**SURFACE THE ENGINE'S OWN DIAGNOSTICS.** The harness reported outcomes and
discarded `info string` lines. Chest was announcing its own failure every time -
`FEHLER: Datei-Schreib-Fehler !` - and it was scored as "no mate found" for a
whole session, invalidating every Chest figure. An engine that says why it
failed is telling you something no outcome code can.

**A MATE SCORE MUST BE POSITIVE, and this cost a whole session's numbers.**
`score mate -19` means the SIDE TO MOVE IS BEING MATED - a LOSS. A helper that
took abs() counted those as solves, and it fed every MateHunter measurement in
the session: lane surveys, the overlap matrix, the portfolio validation, the
MateEval work. On d41+ positions the only mate scores appearing were often
NEGATIVE, so this was not a rare edge case - on 2 of 6 sampled positions EVERY
reported mate score was negative.

It surfaced only because a follow-up asked both engines for the shorter mate a
lane had "found" and NEITHER could find it - an impossible result that pointed
straight at the check. Design measurements so that an impossible outcome is
visible rather than absorbed.

Not necessarily a wash across arms either: a restriction constrains the ATTACKER
while the defender moves freely, so a restricted lane may walk into
being-mated positions more often, which would inflate it specifically.

**CHECK THE RETURNED MATE DISTANCE against the one asked for.** A `mate`
outcome is not a hit. Both Stockfish forks "solved" a mate-in-12 query by
returning the real mate in 14, and Chest returned mate=17 for a mate-in-16 ask.
Any solve count that does not compare `dm` to the requested depth is loose.

**KILLED ENGINES LEAVE STATE.** ChestUCI leaves *.tmp in its own directory and
the next instance dies on it. Clean scratch files before every position and use
a fresh process for engines that persist anything.

**PREFER PAIRED COMPARISONS.** Same binary, same positions, one flag differing.
The MateEval result (stock 3/14, MateMode 4/14, +MateEval 7/14 at d41+) held up;
the unpaired hunt18k-vs-Huntsman comparison flipped sign across three draws.

**Corpus depth: matetrack.epd has 232 positions at d25+, up to mate-in-126.**
Benchmarks stopped at d20 because the scripts were written that way, not because
material ran out.

**Never put a token from a wrapper script's own name in its own `pgrep` guard.**
It matches its own launcher and deadlocks. `runbatch.sh` documents this fix;
it was reintroduced anyway.

Why: every one of these produced a confidently reported wrong answer first.
How to apply: run the check before reporting, not after being questioned.

Related: [[mate-engine-closed-directions]]
