#!/usr/bin/env python3
"""Regression test for the pre-flight hook.

Written as a file rather than inline shell because the hook matches on the
command string, so a shell test that quotes an invocation trips the hook on its
own test harness.

The fixtures are written to a temporary directory rather than named from one
machine's tree, so this runs anywhere: one script that trips a fatal rule
(abs() around a mate score, the sign bug that voided a whole workstream) and
one that does the same job correctly.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "preflight_hook.py")

BAD = "score = -1\nsolved = abs(score) == 2   # a mate score read through abs()\n"
GOOD = "score = -1\nsolved = 0 < score <= 2\n"

tmp = Path(tempfile.mkdtemp(prefix="matebench-hook-"))
fail = 0
try:
    bad = tmp / "bad_measurement.py"
    good = tmp / "good_measurement.py"
    bad.write_text(BAD, encoding="utf-8")
    good.write_text(GOOD, encoding="utf-8")

    CASES = [
        ("script with a fatal rule invoked", "python -u %s --depths 8,10" % bad, 2),
        ("clean script invoked", "python -u %s --depths 8,10" % good, 0),
        ("filename in prose, not invoked", "cat <<EOF\nsee %s notes\nEOF" % bad, 0),
        ("linter itself invoked", "python lint_measurement.py foo.py", 0),
        ("unrelated command", "ls -la /tmp", 0),
    ]

    for label, cmd, want in CASES:
        r = subprocess.run([sys.executable, HOOK],
                           input=json.dumps({"tool_input": {"command": cmd}}),
                           capture_output=True, text=True)
        ok = r.returncode == want
        fail += not ok
        print("  %-34s exit=%d want=%d  %s" % (label, r.returncode, want,
                                               "OK" if ok else "FAIL"))
    print("\n%d/%d passed" % (len(CASES) - fail, len(CASES)))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.exit(1 if fail else 0)
