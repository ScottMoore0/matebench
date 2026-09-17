#!/usr/bin/env bash
# Build MateBench's three reference engines from their public sources, then check
# each against the bench node count its manifest records.
#
#     engines/build.sh [OUT_DIR] [ARCH]
#
# OUT_DIR defaults to ~/mate-engines/bin, where bench/config.py looks for engines;
# ARCH defaults to x86-64-avx2 (see `make help` in a Stockfish src directory).
#
# The sha256 of what you build will differ from the manifests': it depends on the
# compiler and the architecture. The search does not. `bench` reports the same
# node count for any build of the same source under the same options, and the
# runner accepts a binary whose sha256 differs when its bench matches the
# manifest's (SUBMISSION.md). engines/README.md records what was checked.
#
# Needs git, make, g++ (or clang++), python3, curl, and network access:
# the Stockfish sources, MateHunter's patch, and the NNUE networks `make` fetches.
#
# To build from source trees you already have instead of cloning, set SF19_SRC
# (a Stockfish sf_19 checkout), HUNTSMAN_SRC (a Stockfish-old h1 checkout) and
# MATEHUNTER_PATCH (matehunter.patch from MateHunter v0.1.0).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
OUT="${1:-$HOME/mate-engines/bin}"
ARCH="${2:-x86-64-avx2}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

SF19_COMMIT=edb0d9db6731067ec50ce619ff372b463bc4dd5d
HUNTSMAN_COMMIT=136b800533e57fe7e646a53f7d1f726b635e5cc9
PATCH_SHA256=d14cb5c22a513c8eb98c2323b3c0c7b35f92a670d86e8a6036c840c7ef8a821a

checkout() {  # checkout NAME URL TAG COMMIT LOCAL_DIR
  local name=$1 url=$2 tag=$3 commit=$4 local_dir=$5
  if [ -n "$local_dir" ]; then
    cp -r "$local_dir" "$WORK/$name"
  else
    git clone --quiet --branch "$tag" --depth 1 "$url" "$WORK/$name"
  fi
  if [ -d "$WORK/$name/.git" ]; then
    local head; head=$(git -C "$WORK/$name" rev-parse HEAD)
    [ "$head" = "$commit" ] || { echo "$name: expected commit $commit, got $head" >&2; exit 1; }
  fi
}

build() {  # build SRC_DIR EXE: from clean, so a source tree with old objects cannot leak them
  (cd "$1" && make clean > /dev/null 2>&1; make -j"$(nproc)" build ARCH="$ARCH" EXE="$2" > "$WORK/$2.log" 2>&1) \
    || { tail -20 "$WORK/$2.log" >&2; exit 1; }
}

echo "== Stockfish 19"
checkout sf19 https://github.com/official-stockfish/Stockfish.git sf_19 "$SF19_COMMIT" "${SF19_SRC:-}"
cp -r "$WORK/sf19" "$WORK/matehunter19"
build "$WORK/sf19/src" sf19
cp "$WORK/sf19/src/sf19" "$OUT/sf19"

echo "== MateHunter 19 (Stockfish 19 + MateHunter 0.1.0's patch)"
if [ -n "${MATEHUNTER_PATCH:-}" ]; then
  cp "$MATEHUNTER_PATCH" "$WORK/matehunter.patch"
else
  curl -fsSL -o "$WORK/matehunter.patch" \
    https://raw.githubusercontent.com/ScottMoore0/matehunter/v0.1.0/matehunter.patch
fi
echo "$PATCH_SHA256  $WORK/matehunter.patch" | sha256sum -c --quiet
(cd "$WORK/matehunter19/src" && patch -p1 --quiet < "$WORK/matehunter.patch")
build "$WORK/matehunter19/src" matehunter19
cp "$WORK/matehunter19/src/matehunter19" "$OUT/matehunter19"

echo "== Huntsman 1"
checkout huntsman https://github.com/joergoster/Stockfish-old.git h1 "$HUNTSMAN_COMMIT" "${HUNTSMAN_SRC:-}"
build "$WORK/huntsman/src" huntsman
cp "$WORK/huntsman/src/huntsman" "$OUT/huntsman"

echo "== bench under each manifest's options"
python3 - "$OUT" "$ROOT/manifests" <<'EOF'
# The same check bench/submit.py makes (bench_nodes), without its python-chess import.
import json, re, subprocess, sys
from pathlib import Path

def bench_nodes(argv, options):
    cmds = ["uci"] + ["setoption name %s value %s" % (k, v) for k, v in options.items()] + ["isready", "bench", "quit"]
    r = subprocess.run(argv, input=("\n".join(cmds) + "\n").encode(), capture_output=True, timeout=600)
    found = re.findall(r"Nodes searched\s*:\s*(\d+)", (r.stdout + r.stderr).decode(errors="replace"))
    return int(found[-1]) if found else None

out, manifests = Path(sys.argv[1]), Path(sys.argv[2])
bad = 0
for path in sorted(manifests.glob("*.json")):
    m = json.loads(path.read_text(encoding="utf-8"))
    if "bench" not in m:
        continue
    got = bench_nodes([str(out / m["binary"])], m["uci_options"])
    ok = got == m["bench"]
    bad += not ok
    print("  %-32s bench %-9s manifest %-9d %s" % (path.name, got, m["bench"], "OK" if ok else "MISMATCH"))
sys.exit(1 if bad else 0)
EOF
echo "built into $OUT; every bench matches its manifest"
