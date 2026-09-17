#!/usr/bin/env python3
"""Run a submission: any UCI engine, described by a manifest, on the finding and
speed tracks, paired against reference engines described the same way.

    python bench/matebench.py submit submission.json --against manifests/huntsman-1.json
    python bench/matebench.py submit submission.json --print-sha256

The manifest is specified in SUBMISSION.md, and reference manifests are in
manifests/. This script is what makes the rules in SUBMISSION.md and TRACKS.md
hold for an engine nobody here has seen:

  * The binary is identified by its sha256, and a mismatch stops the run.
  * Every option in `uci_options` is set, and the engine must advertise each one.
    An engine accepts `setoption` for a name it does not know and ignores it, so
    an unadvertised option would run an "on" arm at its default. Options the
    engine advertises that the manifest leaves out are listed in the log with
    the defaults that applied.
  * Each arm must first solve a mate in one under its own manifest: a positive
    control on the pipe itself. An engine that reads EOF, or runs with its
    search switched off, answers instantly and would otherwise score as a hard
    position rather than a broken run.
  * A node budget is only allowed when every arm is in the same family; across
    families the budget is a clock (TRACKS.md, Budgets).
  * The engine runs over a live pipe, one fresh process per position, so state
    one search leaves behind cannot reach the next.
  * A mate score counts only if 0 < dm <= N.
  * Every claim is verified. A certificate the submitter supplies is checked by
    MateProver's independent checker (bench/certificates.py). A claim without
    one, or whose certificate fails, is re-proved by MateProver at the claimed
    length. Verified, refuted, unconfirmed and error are kept apart.
  * Positions any arm declares it was tuned on (`tuned_on`) are dropped for
    every arm, so every arm still sees the same positions.
  * The result is paired per band on verified claims: discordant pairs and a
    two-sided sign test. Totals are context.

The checkpoint key carries the binary's sha256, the options, the budget and the
certificate checker's sha256, so a changed binary, setting, budget or checker
never replays an earlier result.
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import queue
import random
import re
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

import certificates
import config

BM = re.compile(r"\bbm\s+#(\d+)")
MATE = re.compile(r"\bscore\s+mate\s+(-?\d+)")
NODES_RE = re.compile(r"\bnodes\s+(\d+)")
PROOF_STRING = re.compile(r"^info\s+string\s+proof\s+(\{.*\})\s*$")
DM_LINE = re.compile(r"; dm (\d+)")
BANDS = [(1, 7), (8, 12), (13, 17), (18, 21), (22, 25), (26, 30), (31, 999)]
REQUIRED = {"name": str, "binary": str, "sha256": str, "source": str, "licence": str,
            "base": str, "uci_options": dict, "tracks": list, "claims": str}
CLAIMS = ("within-N", "shortest")
SCORED_TRACKS = ("finding", "speed")
# The positive control: Rd8 mates, and nothing else does.
CONTROL_FEN = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - -"


class ManifestError(Exception):
    pass


# ------------------------------------------------------------------ manifests

def load_manifest(path):
    path = Path(path)
    try:
        m = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError("%s: %s" % (path, exc))
    if not isinstance(m, dict):
        raise ManifestError("%s: the manifest is not a JSON object" % path)
    for field, kind in REQUIRED.items():
        if field not in m:
            raise ManifestError("%s: missing %r" % (path, field))
        if not isinstance(m[field], kind):
            raise ManifestError("%s: %r must be a %s" % (path, field, kind.__name__))
    if m["claims"] not in CLAIMS:
        raise ManifestError("%s: claims must be one of %s" % (path, ", ".join(CLAIMS)))
    if not re.fullmatch(r"[0-9a-fA-F]{64}", m["sha256"]):
        raise ManifestError("%s: sha256 must be 64 hex digits; get it with "
                            "`python bench/matebench.py submit %s --print-sha256`" % (path, path))
    for name, value in m["uci_options"].items():
        if not isinstance(value, (str, int, float, bool)):
            raise ManifestError("%s: option %r has a value that is not a string, number or boolean"
                                % (path, name))
    cert = m.get("certificates", "none")
    if cert != "none":
        if not isinstance(cert, dict) or cert.get("channel") not in ("info-string", "command"):
            raise ManifestError("%s: certificates must be \"none\", {\"channel\": \"info-string\"} "
                                "or {\"channel\": \"command\", \"argv\": [...]}" % path)
        if cert["channel"] == "command":
            argv = cert.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise ManifestError("%s: a certificate command needs a non-empty argv of strings" % path)
    tuned = m.get("tuned_on", [])
    if not isinstance(tuned, list) or not all(isinstance(x, str) for x in tuned):
        raise ManifestError("%s: tuned_on must be a list of corpus file names" % path)
    m["_path"] = str(path)
    return m


def family_of(m):
    """The family a node budget is comparable within: `family` if given, else the
    first word of `base`, else the engine alone."""
    if isinstance(m.get("family"), str) and m["family"].strip():
        return m["family"].strip().lower()
    words = m["base"].split()
    if words and words[0].lower() != "own":
        return words[0].lower()
    return "own:" + m["name"]


def binary_paths(m):
    """(the file to hash, the path to hand the launcher)."""
    b = m["binary"]
    if os.path.isabs(b) or b.startswith("\\\\"):
        return Path(b), b
    return Path(config.engine(b)), config.engine_exec(b)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def uci_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def digest(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:10]


# ----------------------------------------------------------------------- UCI

class Session:
    """One engine process over a live pipe. Never stdin from a file: an engine at
    EOF answers at once without searching, which scores as a fast failure."""

    def __init__(self, argv):
        self.eof = False
        self.q = queue.Queue()
        # Unbuffered binary pipes: a write to an engine that has exited fails at
        # once, instead of leaving bytes that fail again when the pipe is
        # finalised. Output is decoded as UTF-8 whatever the platform's code page.
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, bufsize=0)
        self.out = io.TextIOWrapper(io.BufferedReader(self.p.stdout), encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.out:
                self.q.put(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            self.q.put(None)

    def send(self, *lines):
        view = memoryview("".join(line + "\n" for line in lines).encode("utf-8"))
        try:
            while view:
                written = self.p.stdin.write(view)
                if not written:
                    return False
                view = view[written:]
            return True
        except (OSError, ValueError):
            return False

    def until(self, prefix, timeout):
        """Lines up to and including the first that starts with `prefix`.

        Returns (lines, found, eof)."""
        lines, end = [], time.monotonic() + timeout
        while not self.eof:
            left = end - time.monotonic()
            if left <= 0:
                return lines, False, False
            try:
                line = self.q.get(timeout=left)
            except queue.Empty:
                return lines, False, False
            if line is None:
                self.eof = True
                break
            lines.append(line)
            if line.startswith(prefix):
                return lines, True, False
        return lines, False, True

    def close(self):
        self.send("quit")
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()
            try:
                self.p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass


def parse_options(lines):
    """{lower-case name: (name, type, default)} from the engine's option lines.
    UCI option names are case-insensitive."""
    out = {}
    for line in lines:
        if not line.startswith("option name "):
            continue
        name, sep, tail = line[len("option name "):].partition(" type ")
        if not sep:
            continue
        kind = tail.split()[0] if tail.split() else ""
        m = re.search(r"\bdefault(?: (.*?))?(?: (?:min|max|var) |$)", tail)
        out[name.strip().lower()] = (name.strip(), kind, (m.group(1) or "") if m else None)
    return out


def probe(argv, timeout=60):
    """(engine id name, advertised options, problem or '')."""
    try:
        s = Session(argv)
    except OSError as exc:
        return "", {}, "cannot start %s (%s)" % (argv, exc)
    try:
        if not s.send("uci"):
            return "", {}, "the engine did not accept input"
        lines, found, eof = s.until("uciok", timeout)
        if not found:
            return "", {}, "no uciok within %d s%s" % (timeout, " (the engine exited)" if eof else "")
        ident = next((l[len("id name "):] for l in lines if l.startswith("id name ")), "")
        return ident, parse_options(lines), ""
    finally:
        s.close()


def search(argv, options, fen, depth, budget, timeout):
    """`go mate depth` on one position in a fresh process.

    The claim is the shortest reported mate with 0 < dm <= depth. A negative mate
    score means the side to move is being mated and is never a solve; a longer
    mate than asked for answers a different question."""
    rec = {"dm": None, "ms": None, "nodes": 0, "status": "ok", "info": [], "proof": None}
    try:
        s = Session(argv)
    except OSError as exc:
        rec["status"] = "cannot start (%s)" % exc
        return rec
    try:
        s.send("uci")
        _, found, eof = s.until("uciok", 60)
        if not found:
            rec["status"] = "exited before uciok" if eof else "no uciok"
            return rec
        s.send(*["setoption name %s value %s" % (k, uci_value(v)) for k, v in options.items()])
        s.send("isready")
        _, found, eof = s.until("readyok", 120)
        if not found:
            rec["status"] = "exited while setting options" if eof else "no readyok"
            return rec
        s.send("ucinewgame", "position fen %s 0 1" % fen, "isready")
        _, found, eof = s.until("readyok", 120)
        if not found:
            rec["status"] = "exited before the search" if eof else "no readyok"
            return rec
        t0 = time.perf_counter()
        s.send("go mate %d %s" % (depth, budget))
        lines, found, eof = s.until("bestmove", timeout)
        rec["ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        if not found:
            rec["status"] = "exited before bestmove" if eof else "timeout"
        for line in lines:
            if not line.startswith("info"):
                continue
            proof = PROOF_STRING.match(line)
            if proof:
                rec["proof"] = proof.group(1)
                continue
            if line.startswith("info string "):
                rec["info"].append(line[len("info string "):][:200])
                continue
            m = MATE.search(line)
            if m:
                dm = int(m.group(1))
                if 0 < dm <= depth:
                    rec["dm"] = dm if rec["dm"] is None else min(rec["dm"], dm)
            n = NODES_RE.search(line)
            if n:
                rec["nodes"] = int(n.group(1))
        rec["info"] = rec["info"][-5:]
        return rec
    finally:
        s.close()


# --------------------------------------------------------------- verification

def prove(prover, fen, claim, nodes):
    """MateProver --direct-depth at the claimed length: verified, refuted,
    unconfirmed (budget ran out, which is not the same as false) or error."""
    try:
        out = subprocess.run(
            prover + ["-z", str(claim), "--direct-depth", "--no-portfolio", "--threads", "1",
                      "--node-limit", str(nodes), "-"],
            input="%s bm #%d;\n" % (fen, claim), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=7200).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "error"
    if "; acn " not in out:
        return "error"          # no result line: a crash must not read as a refutation
    m = DM_LINE.search(out)
    if m and 0 < int(m.group(1)) <= claim:
        return "verified"
    if "timeout" in out:
        return "unconfirmed"
    return "refuted"            # a completed search that found no mate within the claim


def prover_version(prover):
    try:
        out = subprocess.run(prover + ["--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("MateProver could not be run as %s (%s)\n"
                         "  set MATEBENCH_MATEPROVER, or put mateprover in the engine directory"
                         % (prover, exc))
    return out.splitlines()[0] if out else "unknown"


def certificate_by_command(spec, fen, dm):
    """Run the submitter's certificate command for one claim: (stdout or None, problem).

    {fen}, {dm} and {engines} in argv are replaced, and the position is also
    given on stdin as `<fen> bm #<dm>;`, the form MateProver reads."""
    argv = config.launcher() + [a.replace("{fen}", fen).replace("{dm}", str(dm))
                                 .replace("{engines}", config.engines_exec_dir())
                                for a in spec["argv"]]
    try:
        return subprocess.run(argv, input="%s bm #%d;\n" % (fen, dm), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=float(spec.get("timeout", 600))).stdout, ""
    except subprocess.TimeoutExpired:
        return None, "the certificate command timed out"
    except (OSError, ValueError) as exc:
        return None, "the certificate command could not run (%s)" % exc


# ----------------------------------------------------------------------- arms

def prepare_arm(m, launcher=None, probe_timeout=60):
    """Check the binary and the options against the engine itself."""
    hash_path, exec_path = binary_paths(m)
    if not hash_path.exists():
        raise ManifestError("%s: binary not found at %s" % (m["_path"], hash_path))
    actual = sha256_file(hash_path)
    if actual.lower() != m["sha256"].lower():
        raise ManifestError("%s: the binary's sha256 is %s, the manifest says %s"
                            % (m["_path"], actual, m["sha256"]))
    argv = (config.launcher() if launcher is None else list(launcher)) + [exec_path]
    ident, advertised, problem = probe(argv, probe_timeout)
    if problem:
        raise ManifestError("%s: %s" % (m["_path"], problem))
    unknown = [k for k in m["uci_options"] if k.lower() not in advertised]
    if unknown:
        raise ManifestError("%s: the engine does not advertise %s; it would accept the setoption "
                            "and ignore it" % (m["_path"], ", ".join(unknown)))
    set_names = {k.lower() for k in m["uci_options"]}
    defaults = [(name, default) for key, (name, kind, default) in sorted(advertised.items())
                if key not in set_names and kind != "button"]
    return {"name": m["name"], "manifest": m, "argv": argv, "ident": ident,
            "options": dict(m["uci_options"]), "defaults": defaults,
            "family": family_of(m), "sha256": actual.lower()}


def positive_control(arm, budget, timeout):
    """'' if the arm finds the mate in one under its manifest, else what went wrong."""
    rec = search(arm["argv"], arm["options"], CONTROL_FEN, 1, budget, timeout)
    # What the engine says on a position it solves is its baseline: start-up
    # lines, not diagnostics. Only what it says beyond that is reported later.
    arm["baseline_info"] = set(rec["info"])
    if rec["dm"] == 1:
        return ""
    return "positive control failed: %s, status %s%s" % (
        "no mate reported" if rec["dm"] is None else "mate %d" % rec["dm"], rec["status"],
        ("; engine said: " + " | ".join(rec["info"])) if rec["info"] else "")


def run_one(arm, fen, depth, budget, timeout, max_bytes, keep_dir):
    """One search, then the certificate for its claim if the arm supplies them."""
    rec = search(arm["argv"], arm["options"], fen, depth, budget, timeout)
    raw = rec.pop("proof")
    rec["cert"], rec["cert_reason"] = "absent", ""
    spec = arm["manifest"].get("certificates", "none")
    if rec["dm"] is None or spec == "none":
        return rec
    why_absent = "the engine printed no `info string proof` line for its claim"
    if spec["channel"] == "command":
        output, problem = certificate_by_command(spec, fen, rec["dm"])
        raw = certificates.extract(output)
        why_absent = problem or "the certificate command printed no certificate"
    rec["cert"], reason = certificates.verify(fen, rec["dm"], raw, max_bytes)
    rec["cert_reason"] = (why_absent if rec["cert"] == "absent" else reason)[:300]
    if keep_dir and raw is not None:
        out = Path(keep_dir) / arm["sha256"][:16]
        out.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(fen.encode()).hexdigest()[:16]
        (out / ("%s-dm%d.json" % (name, rec["dm"]))).write_text(raw, encoding="utf-8")
    return rec


# ------------------------------------------------------------------ positions

def read_positions(path, lo, hi):
    """[(fen4, depth)] for every positive `bm #N` line with lo <= N <= hi, first occurrence only."""
    out, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.startswith("%"):
            continue
        m = BM.search(line)
        if not m:
            continue
        depth = int(m.group(1))
        fen = " ".join(line.split(" bm ")[0].split()[:4])
        if lo <= depth <= hi and fen not in seen:
            seen.add(fen)
            out.append((fen, depth))
    return out


def fen_set(path):
    out = set()
    for line in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip() and not line.startswith("%"):
            out.add(" ".join(line.split(";")[0].split(" bm ")[0].split()[:4]))
    return out


def checksum_note(path):
    sums = config.CORPORA / "CHECKSUMS.json"
    actual = sha256_file(path)
    if not sums.exists():
        return actual, "no CHECKSUMS.json to compare with"
    recorded = json.loads(sums.read_text(encoding="utf-8")).get(Path(path).name)
    if isinstance(recorded, dict):
        recorded = recorded.get("sha256")
    if recorded is None:
        return actual, "not recorded in CHECKSUMS.json"
    return actual, "matches CHECKSUMS.json" if recorded == actual else "DOES NOT MATCH CHECKSUMS.json"


def shown(path):
    """A path as a log should record it: relative to the repository when inside
    it, else the file name alone, so a log never carries a local directory."""
    try:
        return Path(path).resolve().relative_to(config.ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(str(path)).name


def band_of(depth):
    for lo, hi in BANDS:
        if lo <= depth <= hi:
            return "d%d-%s" % (lo, hi if hi < 999 else "+")
    return "?"


def sign_p(w, l):
    n = w + l
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n) if n else 1.0


# ----------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", help="the submission's manifest")
    ap.add_argument("--against", nargs="*", default=[], metavar="MANIFEST",
                    help="reference engines, each under its own manifest (see manifests/)")
    ap.add_argument("--print-sha256", action="store_true",
                    help="print the sha256 of each manifest's binary and stop")
    ap.add_argument("--corpus", default="chestuci.epd", help="an EPD file in the corpora directory")
    ap.add_argument("--positions", default="",
                    help="an EPD file to run instead of --corpus, such as a held-out split from heldout.py")
    ap.add_argument("--min-depth", type=int, default=8)
    ap.add_argument("--max-depth", type=int, default=999)
    ap.add_argument("--n", type=int, default=0, help="positions to draw; 0 = all in the depth range")
    ap.add_argument("--seed", default="submit", help="names the draw when --n is set")
    budget_group = ap.add_mutually_exclusive_group()
    budget_group.add_argument("--nodes", type=int, default=0,
                              help="node budget per position (default 10,000,000; one family only)")
    budget_group.add_argument("--movetime", type=int, default=0,
                              help="milliseconds per position; required across families")
    ap.add_argument("--verify-nodes", type=int, default=1_000_000,
                    help="MateProver's re-proof budget per claim (TRACKS.md, track 1)")
    ap.add_argument("--max-certificate-mb", type=float, default=256.0)
    ap.add_argument("--jobs", type=int, default=0,
                    help="parallel searches; default 8 under a node budget, 1 under a clock")
    ap.add_argument("--timeout", type=int, default=1800,
                    help="seconds before a node-budgeted search is recorded as a timeout")
    ap.add_argument("--keep-certificates", default="", metavar="DIR",
                    help="also write every submitted certificate to DIR")
    ap.add_argument("--state", default=config.results("submit_state.json"))
    ap.add_argument("--log", default="", help="default: results directory, submit_<name>_<date>.log")
    a = ap.parse_args(argv)

    try:
        manifests = [load_manifest(a.manifest)] + [load_manifest(p) for p in a.against]
    except ManifestError as exc:
        sys.exit("manifest error: %s" % exc)

    if a.print_sha256:
        for m in manifests:
            path, _ = binary_paths(m)
            print("%s  %s" % (sha256_file(path) if path.exists() else "(not found)", path))
        return 0

    names = [m["name"] for m in manifests]
    if len(set(names)) != len(names):
        sys.exit("two manifests share a name; names label the arms, so they must differ")
    for m in manifests:
        if not set(m["tracks"]) & set(SCORED_TRACKS):
            sys.exit("%s lists tracks %s; this runner scores finding and speed "
                     "(minimality and absence are run by vs-prover)" % (m["_path"], m["tracks"]))

    lines_out = []

    def emit(text=""):
        print(text, flush=True)
        lines_out.append(text)

    try:
        arms = [prepare_arm(m) for m in manifests]
    except ManifestError as exc:
        sys.exit("refused: %s" % exc)

    families = sorted({arm["family"] for arm in arms})
    if len(families) > 1 and not a.movetime:
        sys.exit("refused: the arms are in different families (%s). A node is not the same unit of work "
                 "in two different searches, so compare them under --movetime on an idle machine "
                 "(TRACKS.md, Budgets)." % ", ".join(families))
    nodes = a.nodes or (0 if a.movetime else 10_000_000)
    budget = ("movetime %d" % a.movetime) if a.movetime else ("nodes %d" % nodes)
    budget_key = ("t%d" % a.movetime) if a.movetime else str(nodes)
    timeout = (a.movetime / 1000.0 + 120) if a.movetime else a.timeout
    jobs = a.jobs or (1 if a.movetime else 8)
    max_bytes = int(a.max_certificate_mb * 1024 * 1024)

    prover = config.mateprover()
    version = prover_version(prover)
    prover_id = digest([prover, version])
    uses_certs = any(arm["manifest"].get("certificates", "none") != "none" for arm in arms)
    check = certificates.checker() if uses_certs else None
    checker_sha = check.checker_sha256 if check else ""
    for arm in arms:
        cert_spec = arm["manifest"].get("certificates", "none")
        arm["key"] = "%s:%s:%s" % (arm["sha256"][:16], digest(arm["options"]),
                                   digest([cert_spec, checker_sha if cert_spec != "none" else ""]))

    # Positions: the same set for every arm.
    source = Path(a.positions) if a.positions else config.corpus(a.corpus)
    if not source.exists():
        sys.exit("positions not found: %s (fetch with `python bench/matebench.py fetch`)" % source)
    pool = read_positions(source, a.min_depth, a.max_depth)
    excluded = []
    for arm in arms:
        for name in arm["manifest"].get("tuned_on", []):
            tuned_path = config.corpus(name)
            if not tuned_path.exists():
                sys.exit("refused: %s declares tuning on %s, which is not in %s, so its positions "
                         "cannot be excluded" % (arm["name"], name, config.CORPORA))
            tuned = fen_set(tuned_path)
            before = len(pool)
            pool = [(f, d) for f, d in pool if f not in tuned]
            excluded.append((arm["name"], name, before - len(pool)))
    if a.n:
        random.Random(a.seed).shuffle(pool)
        pool = pool[:a.n]
    if not pool:
        sys.exit("no positions left to run")
    corpus_sha, corpus_note = checksum_note(source)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    emit("=== MATEBENCH SUBMISSION RUN %s ===" % stamp)
    emit("  positions   %s, sha256 %s (%s)" % (shown(source), corpus_sha, corpus_note))
    emit("              d%d-%s, %d positions%s" % (a.min_depth, "max" if a.max_depth >= 999 else a.max_depth,
                                                   len(pool), (", drawn with seed %r" % a.seed) if a.n else ""))
    for who, name, count in excluded:
        emit("              %d excluded: %s declares tuning on %s" % (count, who, name))
    profile = {}
    for _, d in pool:
        profile[band_of(d)] = profile.get(band_of(d), 0) + 1
    emit("  bands       " + ", ".join("%s %d" % (b, profile[b]) for b in
                                      [band_of(lo) for lo, _ in BANDS] if b in profile))
    emit("  budget      %s per position, 1 thread unless a manifest says otherwise, %d at a time"
         % (budget.replace("movetime", "movetime (ms)"), jobs))
    if hasattr(os, "getloadavg"):
        emit("  load        %.2f %.2f %.2f" % os.getloadavg())
    elif a.movetime:
        emit("  load        not available on this platform; a clock budget needs an idle machine")
    emit("  verifier    %s (%s), --direct-depth --no-portfolio at %s nodes"
         % (shown(prover[-1]), version, "{:,}".format(a.verify_nodes)))
    if check:
        emit("  certificates checked by %s, sha256 %s, limit %.0f MB"
             % (shown(check.checker_path), check.checker_sha256, a.max_certificate_mb))
    for arm in arms:
        m = arm["manifest"]
        emit("")
        emit("  arm %s%s" % (arm["name"], "  (submission)" if arm is arms[0] else "  (reference)"))
        emit("    engine id   %s" % (arm["ident"] or "(none given)"))
        emit("    binary      %s  sha256 %s" % (m["binary"], arm["sha256"]))
        emit("    family      %s; base %s; licence %s" % (arm["family"], m["base"], m["licence"]))
        emit("    source      %s" % m["source"])
        emit("    claims      %s%s" % (m["claims"], "  (scored here as within-N: this runner does not score "
                                                       "minimality)" if m["claims"] == "shortest" else ""))
        emit("    options     " + ", ".join("%s=%s" % (k, uci_value(v)) for k, v in arm["options"].items()))
        emit("    at default  " + (", ".join("%s=%s" % nd for nd in arm["defaults"]) or "(none)"))
        spec = m.get("certificates", "none")
        emit("    certificates " + ("none" if spec == "none" else spec["channel"] +
                                      (": " + " ".join(spec["argv"]) if spec["channel"] == "command" else "")))
        if m.get("notes"):
            emit("    notes       %s" % m["notes"])

    for arm in arms:
        problem = positive_control(arm, budget, timeout)
        if problem:
            sys.exit("refused: %s: %s" % (arm["name"], problem))
    emit("\n  positive control: every arm found the mate in one under its own manifest")

    state_path = Path(a.state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    st = json.loads(state_path.read_text()) if state_path.exists() else {}
    lock = threading.Lock()

    def save():
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st))
        tmp.replace(state_path)

    run_key = lambda arm, f, d: "run|%s|%s|%s|%d" % (arm["key"], budget_key, f, d)
    work = [(arm, f, d) for f, d in pool for arm in arms if run_key(arm, f, d) not in st]
    emit("  %d searches to run, %d already in %s\n" % (len(work), len(pool) * len(arms) - len(work), shown(state_path)))

    def do_search(item):
        arm, f, d = item
        return run_key(arm, f, d), run_one(arm, f, d, budget, timeout, max_bytes, a.keep_certificates)

    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for k, rec in ex.map(do_search, work):
            with lock:
                st[k] = rec
                done += 1
                if done % 25 == 0 or done == len(work):
                    save()
                    print("     searches %d/%d" % (done, len(work)), flush=True)

    prove_key = lambda f, dm: "prove|%s|%d|%d|%s" % (f, dm, a.verify_nodes, prover_id)
    claims = {}
    for arm in arms:
        for f, d in pool:
            rec = st[run_key(arm, f, d)]
            if rec["dm"] is not None and rec["cert"] != "verified":
                claims[prove_key(f, rec["dm"])] = (f, rec["dm"])
    to_prove = [(k, f, dm) for k, (f, dm) in claims.items() if k not in st]
    emit("  %d claims to re-prove with MateProver, %d already proved" % (len(to_prove), len(claims) - len(to_prove)))
    done = 0
    with ThreadPoolExecutor(max_workers=max(jobs, 1) if not a.movetime else os.cpu_count() or 1) as ex:
        for k, verdict in ex.map(lambda t: (t[0], prove(prover, t[1], t[2], a.verify_nodes)), to_prove):
            with lock:
                st[k] = verdict
                done += 1
                if done % 25 == 0 or done == len(to_prove):
                    save()
                    print("     proofs %d/%d" % (done, len(to_prove)), flush=True)
    save()

    def outcome(arm, f, d):
        rec = st[run_key(arm, f, d)]
        if rec["dm"] is None:
            return "none", ""
        if rec["cert"] == "verified":
            return "verified", "certificate"
        verdict = st[prove_key(f, rec["dm"])]
        return verdict, "mateprover" if verdict == "verified" else ""

    # ---- per arm
    emit("\n  claims and how they were verified")
    emit("  %-24s %6s %7s %8s %6s %6s %8s %11s %5s %9s %8s" % (
        "arm", "n", "claimed", "verified", "cert", "prover", "refuted", "unconfirmed", "error",
        "cert fail", "no end"))
    verified_sets = {}
    for arm in arms:
        counts = {"verified": 0, "refuted": 0, "unconfirmed": 0, "error": 0}
        by_cert = by_prover = claimed = cert_fail = not_ended = 0
        verified_sets[arm["name"]] = set()
        for f, d in pool:
            rec = st[run_key(arm, f, d)]
            if rec["status"] != "ok":
                not_ended += 1
            if rec["cert"] == "rejected":
                cert_fail += 1
            verdict, via = outcome(arm, f, d)
            if verdict == "none":
                continue
            claimed += 1
            counts[verdict] += 1
            if verdict == "verified":
                verified_sets[arm["name"]].add(f)
                by_cert += via == "certificate"
                by_prover += via == "mateprover"
        emit("  %-24s %6d %7d %8d %6d %6d %8d %11d %5d %9d %8d" % (
            arm["name"][:24], len(pool), claimed, counts["verified"], by_cert, by_prover,
            counts["refuted"], counts["unconfirmed"], counts["error"], cert_fail, not_ended))

    for arm in arms:
        refuted = [(f, st[run_key(arm, f, d)]["dm"]) for f, d in pool if outcome(arm, f, d)[0] == "refuted"]
        rejected = [(f, st[run_key(arm, f, d)]["cert_reason"]) for f, d in pool
                    if st[run_key(arm, f, d)]["cert"] == "rejected"]
        stopped = [(f, st[run_key(arm, f, d)]["status"]) for f, d in pool
                   if st[run_key(arm, f, d)]["status"] != "ok"]
        said = sorted({s for f, d in pool if st[run_key(arm, f, d)]["dm"] is None
                       for s in st[run_key(arm, f, d)]["info"]} - arm.get("baseline_info", set()))
        missing = [(f, st[run_key(arm, f, d)]["cert_reason"]) for f, d in pool
                   if arm["manifest"].get("certificates", "none") != "none"
                   and st[run_key(arm, f, d)]["dm"] is not None and st[run_key(arm, f, d)]["cert"] == "absent"]
        if refuted or rejected or stopped or said or missing:
            emit("\n  %s" % arm["name"])
        for f, dm in refuted[:10]:
            emit("    refuted     mate in %d claimed for %s" % (dm, f))
        for f, reason in rejected[:5]:
            emit("    certificate rejected for %s: %s" % (f, reason))
        if missing:
            emit("    no certificate for %d claim(s), so MateProver re-proved them; the first: %s (%s)"
                 % (len(missing), missing[0][1], missing[0][0]))
        for f, status in stopped[:5]:
            emit("    search did not end normally (%s): %s" % (status, f))
        for text in said[:5]:
            emit("    engine said, on a position it did not solve: %s" % text)

    # ---- paired, per band, on verified claims
    sub = arms[0]
    emit("\n  verified per band")
    emit("  %-9s %5s " % ("band", "n") + " ".join("%10s" % arm["name"][:10] for arm in arms))
    for lo, hi in BANDS:
        g = {f for f, d in pool if lo <= d <= hi}
        if g:
            emit("  %-9s %5d " % (band_of(lo), len(g)) +
                 " ".join("%10d" % len(verified_sets[arm["name"]] & g) for arm in arms))

    for ref in arms[1:]:
        sv, rv = verified_sets[sub["name"]], verified_sets[ref["name"]]
        emit("\n  %s against %s, paired on verified claims" % (sub["name"], ref["name"]))
        emit("  %-9s %5s %8s %8s %8s %8s %8s" % ("band", "n", "sub", "ref", "sub only", "ref only", "p"))
        W = L = 0
        for lo, hi in BANDS:
            g = {f for f, d in pool if lo <= d <= hi}
            if not g:
                continue
            w, l = len((sv - rv) & g), len((rv - sv) & g)
            W, L = W + w, L + l
            emit("  %-9s %5d %8d %8d %8d %8d %8.4f" % (band_of(lo), len(g), len(sv & g), len(rv & g), w, l, sign_p(w, l)))
        emit("  %-9s %5d %8d %8d %8d %8d %8.4f" % ("all", len(pool), len(sv), len(rv), W, L, sign_p(W, L)))
        sc = {f for f, d in pool if st[run_key(sub, f, d)]["dm"] is not None}
        rc = {f for f, d in pool if st[run_key(ref, f, d)]["dm"] is not None}
        emit("  reported claims, for context: sub only %d, ref only %d, p = %.4f"
             % (len(sc - rc), len(rc - sc), sign_p(len(sc - rc), len(rc - sc))))

        # ---- speed, on the positions both verified
        shared = sorted(sv & rv)
        times = [(st[run_key(sub, f, d)]["ms"], st[run_key(ref, f, d)]["ms"]) for f, d in pool if f in shared]
        times = [(x, y) for x, y in times if x and y]
        if not times:
            emit("  speed: no position both verified with a recorded time, so no speed result")
            continue
        faster_sub = sum(1 for x, y in times if x < y)
        faster_ref = sum(1 for x, y in times if y < x)
        ratios = [y / x for x, y in times]
        emit("  speed on the %d positions both verified: sub faster on %d, ref faster on %d, p = %.4f; "
             "time ratio ref/sub median %.2f, mean %.2f%s"
             % (len(times), faster_sub, faster_ref, sign_p(faster_sub, faster_ref),
                statistics.median(ratios), statistics.mean(ratios),
                "" if a.movetime else " (under a node budget, time follows speed per node)"))

    emit("\n  The discordant pairs per band are the result. A pooled total can hide two opposite effects.")
    emit("  Unconfirmed claims are not false: supply certificates to have them checked.")
    emit("\n=== MATEBENCH SUBMISSION RUN ENDED ===")

    log_path = Path(a.log) if a.log else Path(config.results("submit_%s_%s.log" % (
        re.sub(r"[^A-Za-z0-9.-]+", "-", sub["name"]).strip("-").lower(), datetime.date.today().isoformat())))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print("  log written to %s" % log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
