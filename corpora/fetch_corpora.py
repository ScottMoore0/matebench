#!/usr/bin/env python3
"""Fetch or locate the corpora. Nothing is vendored; see PROVENANCE.md.

Each corpus is written to this directory as EPD with a `dm N` (or goal-specific)
opcode, the format every script in bench/ reads. A corpus that cannot be
fetched under its terms is *located* from a local install instead, and the
script says so rather than silently substituting.

    python corpora/fetch_corpora.py matetrack
    python corpora/fetch_corpora.py chestuci --chest-dir "C:/.../ChestUCI_V52"
    python corpora/fetch_corpora.py generated --mateprover-repo ../mateprover
"""
import argparse, hashlib, re, shutil, subprocess, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BM = re.compile(r"\bbm\s+#(\d+)")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def matetrack(args):
    url = "https://raw.githubusercontent.com/vondele/matetrack/master/matetrack.epd"
    out = HERE / "matetrack.epd"
    print("  fetching", url)
    urllib.request.urlretrieve(url, out)
    n = sum(1 for l in out.read_text(encoding="utf-8", errors="replace").splitlines() if BM.search(l))
    print("  %s: %d positions with a bm #N opcode, sha256 %s" % (out.name, n, sha(out)))
    print("  NOTE: MateHunter was tuned on this corpus. Reference numbers on it are in-sample.")


def chestuci(args):
    src = Path(args.chest_dir) / "ChestUCI.epd"
    if not src.exists():
        sys.exit("  ChestUCI.epd not found under %s. It ships with ChestUCI; it is not fetched, "
                 "because redistribution needs the authors' permission." % args.chest_dir)
    out = HERE / "chestuci.epd"
    rows = [l for l in src.read_text(encoding="utf-8", errors="replace").splitlines()
            if BM.search(l) and not l.startswith("%")]
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("  %s: %d positions, %d at d>=14, sha256 %s" % (out.name, len(rows),
          sum(1 for l in rows if int(BM.search(l).group(1)) >= 14), sha(out)))
    print("  Every bm #N here is a Chest PROOF: a claim of exactly N needs no further verification.")


def generated(args):
    repo = Path(args.mateprover_repo)
    tool = repo / "tools" / "import_problems.py"
    if not tool.exists():
        sys.exit("  MateProver repository not found at %s (need tools/)." % repo)
    print("  The generated corpus is produced by MateProver's retrograde tools; run them from")
    print("  the MateProver repository and copy the resulting EPD here as generated.epd.")
    print("  Terms: MIT with this repository. Cost triples per doubling of target depth.")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("corpus", choices=["matetrack", "chestuci", "generated"])
ap.add_argument("--chest-dir", default="")
ap.add_argument("--mateprover-repo", default="../mateprover")
a = ap.parse_args()
{"matetrack": matetrack, "chestuci": chestuci, "generated": generated}[a.corpus](a)
