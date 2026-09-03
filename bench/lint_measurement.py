#!/usr/bin/env python3
"""Pre-flight lint for measurement scripts. Catches the errors that have ACTUALLY
recurred in this project, not hypothetical ones.

Every rule below exists because the mistake was made, shipped a wrong conclusion,
and had to be retracted. Prose notes did not prevent any of them from recurring;
this is executable instead.

    lint_measurement.py <script.py> [...]      exit 1 if any ERROR found

Rules are deliberately narrow. A lint that cries wolf gets ignored, which is the
failure mode this is trying to fix.
"""
import re
import sys
from pathlib import Path

ERRORS, WARNS = [], []


def err(f, n, rule, msg, exempt=()):
    if rule in exempt:
        WARNS.append((f, n, rule + " (exempted)", msg))
        return
    ERRORS.append((f, n, rule, msg))


def warn(f, n, rule, msg):
    WARNS.append((f, n, rule, msg))


def check(path):
    # exemptions are collected below, then honoured by _emit
    p = Path(path)
    if not p.exists():
        return
    src = p.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    name = p.name

    # AUDITABLE OPT-OUT. A rule can be wrong for a specific script - trialsgated
    # drops the WHOLE TRIAL when any arm aborts (`if not row: continue`), which
    # PRESERVES pairing, and the UNPAIRED heuristic cannot tell that from a
    # per-arm skip. Suppression requires writing the reason in the file, so the
    # exemption is reviewable rather than silent. Format:
    #     # LINT-OK: RULE-NAME - why this rule does not apply here
    exempt = set(re.findall(r"#\s*LINT-OK:\s*([A-Z-]+)", src))

    has_mate_parse = bool(re.search(r"score\s*\\?s\*\+?\s*mate|score\s+mate", src))

    for i, L in enumerate(lines, 1):
        s = L.strip()
        if s.startswith("#"):
            continue

        # 1. THE SIGN BUG. abs() of a UCI mate score counted `score mate -N`
        #    (the side to move BEING MATED) as a solve. It voided an entire
        #    workstream and was invisible for a dozen runs because nothing in
        #    them could contradict a false positive.
        if re.search(r"\babs\s*\(", L) and re.search(r"mate|MATE", L):
            err(name, i, "SIGN-BUG",
                "abs() near a mate score. A solve requires 0 < dm <= requested.",
                exempt)

        # 2. Mate parsed but never checked for sign/bound.
        # (handled after the loop - needs whole-file view)

        # 3. WALL CLOCK WHERE A DETERMINISTIC BUDGET EXISTS. mateprover ships
        #    --node-limit: "same answer on every run and machine, unlike
        #    --time-limit". Using time made jobs contention-sensitive AND forced
        #    needless serialisation of --threads 1 jobs on a 16-core box.
        if "--time-limit" in L and "mateprover" not in L.lower():
            warn(name, i, "WALL-CLOCK",
                 "--time-limit is nondeterministic; prefer --node-limit.")

        # 4. pgrep/pkill -f matches THIS shell's own command line. It has killed
        #    the session shell twice. Kill by explicit pid.
        if re.search(r"\bp(kill|grep)\s+-\w*f", L):
            warn(name, i, "SELF-MATCH",
                 "pkill/pgrep -f matches its own command line; kill by pid.")

        # 5. CANNED VERDICT WITH NO NULL BRANCH. Six verdict lines in this
        #    project have overstated their data by firing on a threshold with
        #    no branch for "no effect" - most recently 'SINGLE-DIGIT GAP' and
        #    'THE DANGER SCORE IS INERT'.
        if re.search(r"print\(.*(->|=>).*", L) and re.search(
                r"\b(IS|ARE|WINS|BEATS|CONFIRM|PROVEN|CAUSE|INERT|DEAD|REAL)\b", L):
            warn(name, i, "CANNED-VERDICT",
                 "Assertive verdict string - ensure a 'not established' branch exists.")

    # ---- whole-file rules ----

    if has_mate_parse and not re.search(r"0\s*<\s*int|>\s*0\s*and|dm\s*>\s*0|0\s*<\s*dm", src):
        err(name, 0, "NO-DISTANCE-CHECK",
            "Parses a UCI mate score with no `0 < dm <= requested` check.")

    # 12. SUPERSEDED MATEHUNTER PROFILE. ENGINES.md said MateMode was net
    #     negative; 65 scripts set it true anyway, and that profile defined
    #     'the shipped config' for a week while hiding a +21/234 deep gain.
    #     Measured 2026-09-02: MateMode off closes the deficit vs Huntsman.
    #     A WARN, not an error: a few scripts toggle MateMode deliberately.
    if re.search(r'hunt18|matehunter', src, re.I) and re.search(
            r'"MateMode"\s*:\s*"true"', src):
        warn(name, 0, "SUPERSEDED-PROFILE",
             "Sets MateMode=true on a MateHunter arm. Measured net negative"
             " (deep deficit vs Huntsman). Use MateEval=true, MateMode=false.")

    # 6. UNPAIRED COMPARISON - the single most repeated error in this project.
    #    Aggregating each arm over "whatever that arm completed" compares
    #    DIFFERENT ITEM SETS. It made the Chest speed medians meaningless, then
    #    recurred in my own TT sweep hours after I criticised it.
    #
    #    The tell is three things together: several configurations, an aggregate,
    #    and a skip-on-failure `continue` that silently makes the sets diverge.
    #    Keying this on an ARMS list (as the first version did) MISSED the very
    #    script it was written for, because that one looped over a tuple of
    #    budgets instead. Detect the shape, not the naming convention.
    multi_arm = bool(re.search(
        r"\bARMS\b"
        r"|for\s+\w+\s*,\s*\w+\s+in\s+[A-Z_]{3,}"
        r"|for\s+\w+\s+in\s+\([^)]*,[^)]*\)"          # for res in (a, b, c)
        r"|for\s+\w+\s+in\s+\[[^\]]*,[^\]]*\]",       # for x in [a, b, c]
        src))
    aggregates = bool(re.search(r"statistics\.(median|mean)|np\.(median|mean)", src))
    skip_on_fail = bool(re.search(r"if\s+not\s+\w+\s*:\s*\n?\s*continue"
                                  r"|is\s+None\s*:\s*\n?\s*continue"
                                  r"|except[^\n]*:\s*\n\s*continue", src))
    pairs = bool(re.search(r"&=|set\([^)]*\)\s*&|\bshared\b|intersection"
                           r"|discordant|base\[i\]|\ball\s+arms\b", src))
    if multi_arm and aggregates and not pairs:
        sev = (lambda *aa: err(*aa, exempt=exempt)) if skip_on_fail else warn
        sev(name, 0, "UNPAIRED",
            "Several configurations aggregated with no shared/intersection set"
            + (" AND a skip-on-failure continue, so the sets diverge silently."
               if skip_on_fail else ".")
            + " Compare only items ALL arms completed; report discordant pairs.")

    # 7. n not recorded per arm - the specific omission that made the first TT
    #    sweep uninterpretable.
    if multi_arm and aggregates and not re.search(r"len\((got|res|s)\b|completed\s*%d|n=", src):
        warn(name, 0, "NO-N",
             "Does not appear to record n per arm; medians over different "
             "completed sets are not comparable.")

    # 8. Single band. Validating in one regime and generalising killed the
    #    escapes-only result (good at d41+, -7 at d8-12 with 29 discordant).
    if re.search(r"--lo|--depths|band", src) and not re.search(
            r"BANDS|depths\s*=\s*[\"']?\d+\s*,|for\s+lo,\s*hi", src):
        warn(name, 0, "ONE-BAND",
             "Looks like a single band. A default applies at every depth - "
             "check shallow AND deep before changing one.")

    # 9. A VERDICT ON ZERO OBSERVATIONS. Every canned verdict in this project
    #    has checked whether the numbers DIFFER and never whether anything was
    #    MEASURED. The oracle run scored 1/34 for all three arms with ZERO
    #    discordant pairs and printed "CHANNEL CLOSED", because abs(0-0) <= 2.
    #    An empty result satisfied a null-detection condition.
    #
    #    Same shape as "SINGLE-DIGIT GAP" (fired on a median with no sign test)
    #    and "THE DANGER SCORE IS INERT" (fired on a delta inside its own noise
    #    floor). A verdict needs a minimum count of DISCRIMINATING observations,
    #    not merely a small delta.
    verdicts = bool(re.search(
        r"print\([^)]*(CLOSED|OPEN|INERT|DEAD|CONFIRM|PROVEN|IS THE|REAL|"
        r"NOT DEMONSTRATED|GAP)", src))
    counts_pairs = bool(re.search(r"len\(\w+ - \w+\)|discordant|only-", src))
    guards_n = bool(re.search(
        r"min_discordant|NO MEASUREMENT|nd\s*<|< *min_|"
        r"\w+\s*\+\s*\w+\s*<\s*\d+|len\(\w+\)\s*<\s*\d+", src))
    if verdicts and counts_pairs and not guards_n:
        err(name, 0, "VERDICT-NO-N",
            "Prints an assertive verdict with no guard on how many "
            "discriminating observations exist. Zero discordant pairs is NOT a "
            "null - it is an absence of measurement. Require a minimum count "
            "before concluding, and report floor/ceiling when it is not met.")


    # 10. NO POSITIVE CONTROL. A null from an instrument nobody verified is not
    #     a null. The mate_eval counter reported ZERO calls in a normal search -
    #     which would have been a spectacular finding - and the cause was that
    #     the engine emitted an instant bestmove without searching, because
    #     feeding UCI commands from a FILE closes stdin and the engine reads EOF
    #     as quit. Four measurements were void before a positive control caught
    #     it. If a script can report "no effect", it must first show the
    #     instrument registering a KNOWN effect.
    instrument = bool(re.search(r"counter|calls|instrument|probe|stderr", src, re.I))
    reports_null = bool(re.search(r"NO MEASUREMENT|no effect|inert|CLOSED|zero", src, re.I))
    has_control = bool(re.search(r"POSITIVE CONTROL|positive_control|control arm|"
                                 r"sanity|CONTROL FAILED", src, re.I))
    if instrument and reports_null and not has_control:
        warn(name, 0, "NO-POSITIVE-CONTROL",
             "Can report a null from an instrument with no positive control. "
             "Show the instrument registering a KNOWN effect first.")

    # 11. A CONTROL THAT VARIES THE WRONG THING. MISS=+200 was called a
    #     "nonsense control" for the oracle, but every arm in that sweep carried
    #     the FULL correct on-path signal and varied only the off-path baseline,
    #     so it tested the same axis as the other arms. The real control -
    #     shuffling the values - showed the gain was membership, not distance.
    #     Not mechanically detectable; this only flags the WORD so the claim
    #     gets re-read.
    if re.search(r"control", src, re.I) and re.search(
            r"nonsense|random|scrambl|shuffl|placebo", src, re.I) is None:
        warn(name, 0, "CONTROL-UNVERIFIED",
             "Mentions a control but nothing that destroys the signal "
             "(shuffle/randomise). Check the control varies what you think.")


for a in sys.argv[1:]:
    check(a)

for f, n, rule, m in ERRORS:
    print("ERROR  %-18s %s:%s  %s" % (rule, f, n or "-", m))
for f, n, rule, m in WARNS:
    print("warn   %-18s %s:%s  %s" % (rule, f, n or "-", m))

if not ERRORS and not WARNS:
    print("clean")
print("\n%d error(s), %d warning(s)" % (len(ERRORS), len(WARNS)))
sys.exit(1 if ERRORS else 0)
