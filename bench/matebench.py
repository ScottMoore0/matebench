#!/usr/bin/env python3
"""MateBench: one entry point.

Every subcommand is a script in bench/ or corpora/; this file only finds it
and passes the rest of the command line through, so `matebench paired --help`
is `bench/paired_uci.py --help`. Nothing is hidden behind the wrapper, and a
script can always be run directly.

    python bench/matebench.py --list
    python bench/matebench.py fetch chestuci --chest-dir "C:/.../ChestUCI_V52"
    python bench/matebench.py verify-corpora
    python bench/matebench.py heldout corpora/chestuci.epd --salt <round salt>
    python bench/matebench.py submit submission.json --against manifests/huntsman-1.json
    python bench/matebench.py lint my_measurement.py
    python bench/matebench.py paired --help
    python bench/matebench.py table
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name -> (script, one-line purpose, fixed leading arguments)
COMMANDS = {
    "fetch":          ("corpora/fetch_corpora.py", "fetch or locate a corpus; records its sha256 in corpora/CHECKSUMS.json", []),
    "verify-corpora": ("corpora/fetch_corpora.py", "check every present corpus against corpora/CHECKSUMS.json", ["verify"]),
    "heldout":        ("bench/heldout.py",         "split a corpus into development and held-out halves by salted hash (docs/HELDOUT.md)", []),
    "lint":           ("bench/lint_measurement.py","pre-flight lint: refuses a script that repeats a known-fatal measurement error", []),
    "submit":         ("bench/submit.py",         "tracks 1-2 for any UCI engine under a submission.json manifest; certificates accepted", []),
    "paired":         ("bench/paired_uci.py",      "tracks 1-2 within a family: two UCI arms, node budget, paired per band", []),
    "vs-prover":      ("bench/vs_prover.py",       "tracks 1-2 across families: a UCI arm against MateProver, wall-clock, claims verified", []),
    "vs-stockfish":   ("bench/vs_stockfish.py",    "MateHunter against stock Stockfish 19 on ChestUCI, with the MateEval channel arms", []),
    "verify-budget":  ("bench/verify_budget.py",   "re-derive the verification ceiling (bimodal cost; 1M nodes)", []),
    "headroom":       ("bench/lane_headroom.py",   "headroom of a candidate portfolio lane at a real lane budget", []),
    "beam":           ("bench/beam_experiment.py", "the defender-pruning control; reference result: strictly dominated", []),
    "table":          ("bench/results_table.py",   "regenerate results/reference/TABLES.md from the dated logs", []),
}


def usage(stream=sys.stdout):
    print(__doc__.strip(), file=stream)
    print("\ncommands:", file=stream)
    for name, (script, purpose, fixed) in COMMANDS.items():
        present = "" if (ROOT / script).exists() else "   [script missing]"
        print("  %-15s %s%s" % (name, purpose, present), file=stream)


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "--list", "list"):
        usage()
        return 0
    name = argv[0]
    if name not in COMMANDS:
        print("unknown command %r" % name, file=sys.stderr)
        usage(sys.stderr)
        return 2
    script, _, fixed = COMMANDS[name]
    path = ROOT / script
    if not path.exists():
        print("%s: script %s is not in this checkout" % (name, script), file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(path)] + fixed + argv[1:], cwd=str(ROOT))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
