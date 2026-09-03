#!/usr/bin/env python3
"""Regression test for the pre-flight hook.

Written as a file rather than inline shell because the hook matches on the
command string, so a shell test that quotes an invocation trips the hook on its
own test harness.
"""
import json
import subprocess
import sys

HOOK = str(Path(__file__).resolve().parent / "preflight_hook.py")

CASES = [
    ("known-buggy script invoked", "python -u mp3_tt.py --depths 8,10", 2),
    ("corrected script invoked", "python -u mp3b_tt.py --depths 8,10", 0),
    ("filename in prose, not invoked", "cat <<EOF\nsee mp3_tt.py notes\nEOF", 0),
    ("linter itself invoked", "python lint_measurement.py foo.py", 0),
    ("unrelated command", "ls -la /tmp", 0),
]

fail = 0
for label, cmd, want in CASES:
    r = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"tool_input": {"command": cmd}}),
                       capture_output=True, text=True)
    ok = r.returncode == want
    fail += not ok
    print("  %-34s exit=%d want=%d  %s" % (label, r.returncode, want,
                                           "OK" if ok else "FAIL"))
print("\n%d/%d passed" % (len(CASES) - fail, len(CASES)))
sys.exit(1 if fail else 0)
