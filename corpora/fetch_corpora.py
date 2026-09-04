#!/usr/bin/env python3
"""Fetch or locate the corpora, and record what was fetched. Nothing is vendored;
see PROVENANCE.md.

Each corpus is written to this directory as EPD with a `bm #N` (or goal-specific)
opcode, the format every script in bench/ reads. A corpus that cannot be
fetched under its terms is *located* from a local install instead, and the
script says so rather than silently substituting.

Every fetch records the file's full sha256 and position count in CHECKSUMS.json.
`verify` recomputes them for every corpus that is present, so a result log can
be tied to the exact corpus bytes it was produced on.

    python corpora/fetch_corpora.py matetrack
    python corpora/fetch_corpora.py chestuci --chest-dir "C:/.../ChestUCI_V52"
    python corpora/fetch_corpora.py generated --mateprover-repo ../mateprover
    python corpora/fetch_corpora.py verify
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKSUMS = HERE / "CHECKSUMS.json"
BM = re.compile(r"bm[ ]+#([0-9]+)")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def count_positions(p):
    return sum(1 for l in Path(p).read_text(encoding="utf-8", errors="replace").splitlines()
               if BM.search(l) and not l.startswith("%"))


def load_checksums():
    if CHECKSUMS.exists():
        return json.loads(CHECKSUMS.read_text(encoding="utf-8"))
    return {}


def record(name, path, source):
    data = load_checksums()
    data[name] = {
        "file": Path(path).name,
        "sha256": sha(path),
        "positions": count_positions(path),
        "source": source,
        "recorded": datetime.date.today().isoformat(),
    }
    CHECKSUMS.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("  recorded in CHECKSUMS.json: %s sha256 %s, %d positions"
          % (data[name]["file"], data[name]["sha256"][:16], data[name]["positions"]))


def matetrack(args):
    url = "https://raw.githubusercontent.com/vondele/matetrack/master/matetrack.epd"
    out = HERE / "matetrack.epd"
    print("  fetching", url)
    urllib.request.urlretrieve(url, out)
    print("  %s: %d positions with a bm #N opcode" % (out.name, count_positions(out)))
    print("  NOTE: MateHunter was tuned on this corpus. Reference numbers on it are in-sample.")
    record("matetrack", out, url)


def chestuci(args):
    src = Path(args.chest_dir) / "ChestUCI.epd"
    if not src.exists():
        sys.exit("  ChestUCI.epd not found under %s. It ships with ChestUCI; it is not fetched, "
                 "because redistribution needs the authors' permission." % args.chest_dir)
    out = HERE / "chestuci.epd"
    rows = [l for l in src.read_text(encoding="utf-8", errors="replace").splitlines()
            if BM.search(l) and not l.startswith("%")]
    out.write_text(chr(10).join(rows) + chr(10), encoding="utf-8")
    print("  %s: %d positions, %d at d>=14" % (out.name, len(rows),
          sum(1 for l in rows if int(BM.search(l).group(1)) >= 14)))
    print("  Every bm #N here is a Chest PROOF: a claim of exactly N needs no further verification.")
    record("chestuci", out, "local ChestUCI install: " + str(src))


def generated(args):
    repo = Path(args.mateprover_repo)
    tool = repo / "tools" / "import_problems.py"
    if not tool.exists():
        sys.exit("  MateProver repository not found at %s (need tools/)." % repo)
    out = HERE / "generated.epd"
    print("  The generated corpus is produced by MateProver's retrograde tools; run them from")
    print("  the MateProver repository and copy the resulting EPD here as generated.epd.")
    print("  Terms: MIT with this repository. Cost triples per doubling of target depth.")
    if out.exists():
        record("generated", out, "MateProver retro tools, " + str(repo))
    else:
        print("  (generated.epd not present yet; nothing recorded)")


def verify(args):
    data = load_checksums()
    if not data:
        print("  CHECKSUMS.json is empty or absent: nothing has been fetched from this checkout.")
        return 0
    bad = 0
    for name, entry in sorted(data.items()):
        path = HERE / entry["file"]
        if not path.exists():
            print("  %-10s absent   (recorded %s, %d positions)" % (name, entry["sha256"][:16], entry["positions"]))
            continue
        got = sha(path)
        if got == entry["sha256"]:
            print("  %-10s OK       sha256 %s, %d positions" % (name, got[:16], entry["positions"]))
        else:
            bad += 1
            print("  %-10s MISMATCH recorded %s, on disk %s (%d positions on disk)"
                  % (name, entry["sha256"][:16], got[:16], count_positions(path)))
    if bad:
        print("  %d corpus file(s) differ from what was recorded. Results produced on them"
              " are not tied to the recorded checksum." % bad)
    return 1 if bad else 0


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("corpus", choices=["matetrack", "chestuci", "generated", "verify"])
ap.add_argument("--chest-dir", default="")
ap.add_argument("--mateprover-repo", default="../mateprover")
a = ap.parse_args()
sys.exit({"matetrack": matetrack, "chestuci": chestuci, "generated": generated, "verify": verify}[a.corpus](a) or 0)
