"""Paths for the harness. Nothing here assumes a particular machine.

Set these in the environment (or edit the defaults) before running anything in
bench/:

    MATEBENCH_ENGINES   directory holding the engine binaries
    MATEBENCH_RESULTS   where logs and checkpoint state are written
    MATEBENCH_CORPORA   where fetch_corpora.py put the EPD files
    MATEBENCH_MATEPROVER_REPO   a MateProver checkout, for tools/verify_proof.py
                                (https://github.com/ScottMoore0/mateprover, v0.2.0)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = Path(os.environ.get("MATEBENCH_ENGINES", Path.home() / "mate-engines" / "bin"))
RESULTS = Path(os.environ.get("MATEBENCH_RESULTS", ROOT / "results" / "state"))
CORPORA = Path(os.environ.get("MATEBENCH_CORPORA", ROOT / "corpora"))
MATEPROVER_REPO = Path(os.environ.get("MATEBENCH_MATEPROVER_REPO", ROOT.parent / "mateprover"))
RESULTS.mkdir(parents=True, exist_ok=True)


def engine(name):
    return str(ENGINES / name)


def results(name):
    return str(RESULTS / name)


def corpus(name):
    return CORPORA / name
