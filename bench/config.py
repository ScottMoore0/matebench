"""Paths for the harness. Nothing here assumes a particular machine.

Set these in the environment (or edit the defaults) before running anything in
bench/:

    MATEBENCH_ENGINES   directory holding the engine binaries
    MATEBENCH_RESULTS   where logs and checkpoint state are written
    MATEBENCH_CORPORA   where fetch_corpora.py put the EPD files
    MATEBENCH_MATEPROVER_REPO   a MateProver checkout, for tools/verify_proof.py
                                (https://github.com/ScottMoore0/mateprover, v0.2.0)

Only for engines that run somewhere other than where the harness runs, such as
under WSL or in a container (used by bench/submit.py):

    MATEBENCH_LAUNCHER      command prefix that starts an engine, e.g. `wsl -e`,
                            or a JSON list of arguments
    MATEBENCH_ENGINES_EXEC  the engine directory as the launcher sees it, e.g.
                            /home/me/mate-engines/bin; binaries are still hashed
                            through MATEBENCH_ENGINES
    MATEBENCH_MATEPROVER    a MateProver binary to run directly, without the
                            launcher; by default it is `mateprover` in the engine
                            directory, started through the launcher
"""
import json
import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = Path(os.environ.get("MATEBENCH_ENGINES", Path.home() / "mate-engines" / "bin"))
RESULTS = Path(os.environ.get("MATEBENCH_RESULTS", ROOT / "results" / "state"))
CORPORA = Path(os.environ.get("MATEBENCH_CORPORA", ROOT / "corpora"))
MATEPROVER_REPO = Path(os.environ.get("MATEBENCH_MATEPROVER_REPO", ROOT.parent / "mateprover"))
LAUNCHER = os.environ.get("MATEBENCH_LAUNCHER", "")
ENGINES_EXEC = os.environ.get("MATEBENCH_ENGINES_EXEC", "")
MATEPROVER = os.environ.get("MATEBENCH_MATEPROVER", "")
RESULTS.mkdir(parents=True, exist_ok=True)


def engine(name):
    return str(ENGINES / name)


def results(name):
    return str(RESULTS / name)


def corpus(name):
    return CORPORA / name


def launcher():
    """The command prefix that starts an engine; empty unless MATEBENCH_LAUNCHER is set."""
    if not LAUNCHER.strip():
        return []
    if LAUNCHER.lstrip().startswith("["):
        return list(json.loads(LAUNCHER))
    return shlex.split(LAUNCHER)


def engines_exec_dir():
    """The engine directory as the launcher sees it."""
    return ENGINES_EXEC.rstrip("/\\") if ENGINES_EXEC else str(ENGINES)


def engine_exec(name):
    """The path to hand the launcher for engine `name`: the file engine(name) hashes."""
    if not ENGINES_EXEC:
        return engine(name)
    return engines_exec_dir() + "/" + name


def mateprover():
    """The argument prefix that runs MateProver."""
    if MATEPROVER:
        return [MATEPROVER]
    return launcher() + [engine_exec("mateprover")]
