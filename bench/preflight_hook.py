#!/usr/bin/env python3
"""PreToolUse hook: refuse to launch a measurement script that fails the lint.

WHY THIS EXISTS. Prose notes did not stop me repeating measurement errors. In a
single session I reintroduced the unpaired-medians bug hours after criticising
it in someone else's numbers, caused the CRLF damage I had just flagged as a
risk, killed my own shell twice with pgrep -f, and shipped a canned verdict line
that overstated its data for the sixth time in this project. Documentation I am
supposed to remember to read is not a control. This is.

It is deliberately narrow: it blocks ONLY on lint ERRORs (the errors that have
each already produced a retracted conclusion), and stays silent otherwise. A
hook that fires on everything gets disabled, which is the failure mode this is
trying to avoid.

Reads the tool call on stdin, finds any .py the command launches, lints those,
and exits 2 to block if an ERROR is found.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINT = HERE / "lint_measurement.py"

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

cmd = (payload.get("tool_input") or {}).get("command") or ""
if not cmd or "python" not in cmd:
    sys.exit(0)

# Only guard the measurement tree; leave everything else alone.
#
# Match only scripts actually INVOKED - i.e. immediately after a python
# interpreter, allowing flags like -u. The first version matched any *.py
# appearing anywhere in the command, so it fired on a filename quoted inside
# heredoc DOCUMENTATION and blocked a memory-file write. A guard that trips on
# prose gets switched off, which defeats it.
SELF = {"lint_measurement.py", "preflight_hook.py"}
names = re.findall(r"python[0-9.]*(?:\s+-[A-Za-z]+)*\s+([A-Za-z0-9_./\\-]+\.py)", cmd)
targets = []
for n in names:
    base = Path(n).name
    if base in SELF:          # never lint the linter: its rule definitions
        continue              # contain the very literals they match on
    p = HERE / base
    if p.exists():
        targets.append(str(p))
if not targets:
    sys.exit(0)

try:
    r = subprocess.run([sys.executable, str(LINT)] + targets,
                       capture_output=True, text=True, timeout=60)
except Exception:
    sys.exit(0)

if r.returncode == 1:
    errs = [l for l in (r.stdout or "").splitlines() if l.startswith("ERROR")]
    sys.stderr.write(
        "BLOCKED by measurement pre-flight lint.\n\n"
        + "\n".join(errs)
        + "\n\nEach of these rules exists because the mistake was made, produced a\n"
          "wrong conclusion, and had to be retracted. Fix the script, or if the\n"
          "rule is genuinely wrong here, say so explicitly rather than working\n"
          "around it silently.\n")
    sys.exit(2)

sys.exit(0)
