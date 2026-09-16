# Measurement protocol

These rules apply to every measurement in this repository. Each one exists
because a result was reported under the opposite practice and later overturned,
and the case is given with each rule, because the case is what makes the rule
specific. `bench/lint_measurement.py` enforces the mechanical ones, and
`bench/submit.py` applies the ones marked below to every submission.

## Replicate in a different depth band

Replicating on fresh positions from the same band tests sampling noise, not
generality. Fresh mate-in-20 positions twice confirmed an experimental
MateHunter 18 build ahead of Huntsman; the adjacent bands reversed it.

## Make the verdict test the quantity that matters

A check of `union > best_single` reported a portfolio as worth building when the
entire gain came from two alpha-beta engines and the DFPN prover contributed
nothing. A check of `delta >= 0` reported a null result as a gain. Test the
specific quantity, and never let zero read as a pass.

## Read the table, not the verdict line

Five printed verdicts have overstated their data:

- `union > best_single` said a portfolio was worth building when DFPN contributed 0;
- `delta >= 0` called a null result a gain;
- `only_dfpn > 0` said DFPN earned its place on 2 positions in 100;
- a fixed hint named `SearchDepth` as the cause whatever the numbers were;
- `max()` over tied values reported a peak in the middle of a plateau.

Print the table and read it. A verdict line is a reminder of what was tested,
not the finding.

## Compare node counts only under a node budget

Under a time limit the faster binary searches further, so identical node counts
are impossible and differing ones prove nothing.

## Confirm an option changes the search before measuring it

Four Chest options gave byte-identical node counts, which looked like unknown
option names being ignored. All were real and advertised; they changed nothing
because each already defaulted to the value being set. The identical counts had
a third cause: the engine was aborting on a stale scratch file and never
searching at all. Read the option list from the engine, and its defaults, before
forming a hypothesis about it.

`bench/submit.py` refuses any manifest option the engine does not advertise,
and runs a positive control before anything is measured.

## Profile before naming a hotspot

Per-node allocation was named as the clearest win because move generation ranked
high in a profile. Allocation was 3.9% of the time; the real costs were the
transposition table (about 21.6%) and a locale-aware `tolower` (5.4%).

## Record the engine's own diagnostics

A harness that kept only outcomes discarded Chest's `info string` lines. Chest
was reporting its own failure on every position, `FEHLER: Datei-Schreib-Fehler !`
(a file write error), and every position was scored as "no mate found" until the
lines were read. An engine that says why it failed is giving information no
outcome code carries.

`bench/submit.py` reports what an engine prints on an unsolved position beyond
what it prints on a solved one.

## A mate score must be positive

`score mate -19` means the side to move is being mated: a loss, not a solve. A
helper that took the absolute value counted those as solves, and every
MateHunter measurement that used it had to be discarded. It was not a rare case:
on mate-in-41-and-deeper positions the only mate scores were often negative, and
on 2 of 6 sampled positions every reported score was.

It surfaced only because a follow-up asked both engines for the shorter mate a
restricted search had supposedly found, and neither could find it. Design
measurements so that an impossible outcome is visible rather than absorbed.

The error does not cancel between arms. A restriction constrains the attacker
while the defender moves freely, so a restricted search can walk into
being-mated positions more often, which inflates that arm in particular.

`bench/submit.py` accepts a mate score only if `0 < dm <= N`.

## Check the returned mate distance against the one requested

A reported mate is not a hit. Both Stockfish forks "solved" a mate-in-12 query
by returning the real mate in 14, and Chest returned mate in 17 for a
mate-in-16 query. A solve count that does not compare the returned distance with
the requested one is loose.

## Start each position in a fresh process

A killed ChestUCI leaves `.tmp` files in its own directory, and the next
instance dies on them. Clean scratch files before every position, and use a
fresh process for any engine that keeps state on disk.

`bench/submit.py` starts every search in a fresh process.

## Prefer paired comparisons

Compare the same binary on the same positions with one setting changed. The
MateEval result (stock 3 of 14, MateMode 4 of 14, MateEval 7 of 14, at mate in 41
and deeper) held up; an unpaired comparison of the same experimental MateHunter
18 build against Huntsman flipped sign across three draws.

`bench/submit.py` gives every arm the same positions and reports discordant
pairs with a sign test.

## Use the whole depth range of a corpus

matetrack has 232 positions at mate in 25 or deeper, up to mate in 126.
Benchmarks stopped at mate in 20 because the scripts were written that way, not
because the positions ran out.

## A process guard must not match its own command line

A wrapper that checks for a running copy of itself with `pgrep -f` matches its
own launcher when the pattern contains a token from its own name, and waits for
itself forever. Match on a process id instead.
