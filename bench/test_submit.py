#!/usr/bin/env python3
"""Offline tests for bench/submit.py and bench/certificates.py.

    MATEBENCH_MATEPROVER_REPO=/path/to/mateprover python bench/test_submit.py

No real engine is needed. The engines and the prover are small python-chess
programs written to a temporary directory and started through
MATEBENCH_LAUNCHER, and they solve their positions by exhaustive search, so
every mate distance a test expects is exact rather than assumed. The one real
component is MateProver's certificate checker, tools/verify_proof.py, because
checking what it accepts and rejects is the point.

Each test that expects a refusal or a rejection also has a matching case that
must pass, so a check that rejects everything cannot pass the suite.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="matebench-test-"))
for name in ("engines", "corpora", "results", "certs"):
    (TMP / name).mkdir()
os.environ["MATEBENCH_ENGINES"] = str(TMP / "engines")
os.environ["MATEBENCH_CORPORA"] = str(TMP / "corpora")
os.environ["MATEBENCH_RESULTS"] = str(TMP / "results")
os.environ["MATEBENCH_LAUNCHER"] = json.dumps([sys.executable])
os.environ.pop("MATEBENCH_ENGINES_EXEC", None)
os.environ.pop("MATEBENCH_MATEPROVER", None)
os.environ.pop("FAKE_PROVER", None)
sys.path.insert(0, str(HERE))

import certificates  # noqa: E402
import config        # noqa: E402
import submit        # noqa: E402

# Distances established by exhaustive search, not by assumption.
M1A = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - -"
M1B = "5k2/8/5K2/8/8/8/8/R7 w - -"
M2A = "7k/8/5K2/8/8/8/8/6R1 w - -"
M2B = "k7/8/2K5/8/8/8/8/1R6 w - -"
NOMATE = "7k/7p/8/8/8/8/8/K5R1 w - -"      # no mate within 3
M2WIDE = "7k/8/5K2/8/8/p7/8/6R1 w - -"    # mate in 2 with a two-reply defender node

SOLVER = r'''
import chess

def mates_in(b, n):
    for mv in list(b.legal_moves):
        b.push(mv)
        if b.is_checkmate():
            b.pop(); return True
        if n > 1 and not b.is_game_over():
            ok = True
            for r in list(b.legal_moves):
                b.push(r); good = mates_in(b, n - 1); b.pop()
                if not good:
                    ok = False; break
            if ok:
                b.pop(); return True
        b.pop()
    return False

def distance(fen, limit):
    b = chess.Board(fen + " 0 1")
    for n in range(1, min(limit, 3) + 1):
        if mates_in(b, n):
            return n
    return None

def certificate(b, n):
    for mv in list(b.legal_moves):
        b.push(mv)
        if b.is_checkmate():
            b.pop(); return {"a": mv.uci(), "mate": True}
        if n > 1 and not b.is_game_over():
            replies = []
            for r in list(b.legal_moves):
                b.push(r); sub = certificate(b, n - 1); b.pop()
                if sub is None:
                    replies = None; break
                replies.append({"r": r.uci(), "p": sub})
            if replies:
                b.pop(); return {"a": mv.uci(), "d": replies}
        b.pop()
    return None
'''

ENGINE = SOLVER + r'''
import json, sys
opts = {"mode": "honest", "cert": "none"}
fen = None
for raw in sys.stdin:
    line = raw.strip()
    if line == "uci":
        print("id name Fake Engine")
        print("option name Threads type spin default 1 min 1 max 512")
        print("option name Hash type spin default 16 min 1 max 1024")
        print("option name Mode type string default honest")
        print("option name Cert type string default none")
        print("option name Clear Hash type button")
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("setoption name "):
        name, _, value = line[len("setoption name "):].partition(" value ")
        opts[name.strip().lower()] = value.strip()
    elif line.startswith("position fen "):
        fen = " ".join(line[len("position fen "):].split()[:4])
    elif line.startswith("go mate "):
        n = int(line.split()[2])
        mode, cert = opts["mode"], opts["cert"]
        if mode == "eof":
            sys.exit(0)
        d = distance(fen, n)
        claim = {"honest": d, "negative": d, "overlong": n + 1, "silent": None,
                 "liar": 1, "plus-one": (d + 1) if d else None}[mode]
        if claim is not None:
            sign = -1 if mode == "negative" else 1
            print("info depth 5 score mate %d nodes 1234 time 1" % (sign * claim))
        if cert != "none" and d is not None:
            node = certificate(chess.Board(fen + " 0 1"), d)
            if cert == "forged":
                if "d" in node:
                    node["d"] = node["d"][1:]
                else:
                    b = chess.Board(fen + " 0 1")
                    node["a"] = next(m.uci() for m in b.legal_moves if m.uci() != node["a"])
            text = "{oops}" if cert == "garbage" else json.dumps(node, separators=(",", ":"))
            print("info string proof " + text)
        if mode in ("silent",):
            print("info string evaluation file not found")
        print("bestmove 0000", flush=True)
    elif line == "bench":
        # Like Stockfish: the count goes to stderr and depends on the options.
        print("Nodes searched  : %d" % (1000 + 7 * len(opts["mode"])), file=sys.stderr, flush=True)
    elif line == "quit":
        break
'''

PROVER = SOLVER + r'''
import os, sys
args = sys.argv[1:]
if "--version" in args:
    print("mateprover 0.2.0 (test double)"); sys.exit(0)
if "--emit-proof" in args:
    import json
    for raw in sys.stdin:
        fen = " ".join(raw.split(" bm ")[0].split()[:4])
        n = int(args[args.index("-z") + 1])
        node = certificate(chess.Board(fen + " 0 1"), n)
        if node:
            print("%s; acn 10; acs 0.0; bm %s; dm %d; pv x; proof %s;" % (fen, node["a"], n, json.dumps(node)))
    sys.exit(0)
n = int(args[args.index("-z") + 1])
for raw in sys.stdin:
    fen = " ".join(raw.split(" bm ")[0].split()[:4])
    if os.environ.get("FAKE_PROVER") == "timeout":
        print("%s; acn 1000000; acs 1.0; timeout;" % fen); continue
    if os.environ.get("FAKE_PROVER") == "crash":
        continue
    d = distance(fen, n)
    if d is None:
        print("%s; acn 500; acs 0.1;" % fen)
    else:
        print("%s; acn 10; acs 0.0; bm x; dm %d; pv x;" % (fen, d))
'''

(TMP / "engines" / "fake").write_text(ENGINE, encoding="utf-8")
(TMP / "engines" / "mateprover").write_text(PROVER, encoding="utf-8")
FAKE_SHA = submit.sha256_file(TMP / "engines" / "fake")

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("  %s  %s%s" % ("ok  " if condition else "FAIL", name, ("  (%s)" % detail) if detail and not condition else ""))


def manifest(path_name, **over):
    m = {"name": "fake", "binary": "fake", "sha256": FAKE_SHA, "source": "test", "licence": "MIT",
         "base": "Test 1", "family": "test", "uci_options": {"Threads": 1, "Mode": "honest"},
         "tracks": ["finding", "speed"], "claims": "within-N"}
    m.update(over)
    for k in [k for k, v in over.items() if v is None]:
        del m[k]
    p = TMP / path_name
    p.write_text(json.dumps(m), encoding="utf-8")
    return p


def refused(fn):
    try:
        fn()
    except (submit.ManifestError, SystemExit) as exc:
        return str(exc)
    return ""


def quiet(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = fn(*args)
        except SystemExit as exc:
            code = exc.code
    return code, buf.getvalue()


def test_manifests():
    print("\nmanifests")
    good = manifest("good.json")
    check("a complete manifest loads", submit.load_manifest(good)["name"] == "fake")
    check("a missing field is refused", "missing 'licence'" in refused(
        lambda: submit.load_manifest(manifest("m1.json", licence=None))))
    check("a malformed sha256 is refused", "64 hex digits" in refused(
        lambda: submit.load_manifest(manifest("m2.json", sha256="abc"))))
    check("an unknown claims value is refused", "claims must be" in refused(
        lambda: submit.load_manifest(manifest("m3.json", claims="best"))))
    check("a certificate command without argv is refused", "argv" in refused(
        lambda: submit.load_manifest(manifest("m4.json", certificates={"channel": "command"}))))
    check("tuned_on must be a list", "tuned_on" in refused(
        lambda: submit.load_manifest(manifest("m5.json", tuned_on="matetrack.epd"))))
    check("family: explicit field wins", submit.family_of({"family": "Stockfish", "base": "own", "name": "x"}) == "stockfish")
    check("family: first word of base", submit.family_of({"base": "Stockfish 19", "name": "x"}) == "stockfish")
    check("family: an engine with its own base is its own family",
          submit.family_of({"base": "own", "name": "Chest"}) == "own:Chest")


def test_arms():
    print("\narms")
    m = submit.load_manifest(manifest("arm.json"))
    arm = submit.prepare_arm(m)
    check("a matching binary with advertised options is accepted", arm["sha256"] == FAKE_SHA)
    names = [n for n, _ in arm["defaults"]]
    check("advertised options left at default are recorded", "Hash" in names and "Cert" in names)
    check("options the manifest sets are not listed as defaults", "Threads" not in names and "Mode" not in names)
    check("button options are not listed as defaults", "Clear Hash" not in names)
    wrong = submit.load_manifest(manifest("sha.json", sha256="0" * 64))
    check("a sha256 mismatch is refused", "sha256 is" in refused(lambda: submit.prepare_arm(wrong)))
    honest_bench = 1000 + 7 * len("honest")
    rebuilt = submit.load_manifest(manifest("rebuilt.json", sha256="0" * 64, bench=honest_bench))
    check("a sha256 mismatch with a matching bench is accepted as a rebuild",
          not refused(lambda: submit.prepare_arm(rebuilt))
          and "rebuild" in submit.prepare_arm(rebuilt)["identity"])
    offbench = submit.load_manifest(manifest("offbench.json", sha256="0" * 64, bench=honest_bench + 1))
    check("a sha256 mismatch with a different bench is refused",
          "not the same search" in refused(lambda: submit.prepare_arm(offbench)))
    other_opts = submit.load_manifest(manifest("otheropts.json", sha256="0" * 64, bench=honest_bench,
                                               uci_options={"Threads": 1, "Mode": "liar"}))
    check("bench is taken under the manifest's own options",
          "not the same search" in refused(lambda: submit.prepare_arm(other_opts)))
    check("a matching sha256 needs no bench", arm["identity"] == "sha256 matches the manifest")
    check("bench must be a positive integer", "bench must be" in refused(
        lambda: submit.load_manifest(manifest("badbench.json", bench="5314178"))))
    ghost = submit.load_manifest(manifest("ghost.json", uci_options={"MateEval": "true"}))
    check("an option the engine does not advertise is refused",
          "does not advertise MateEval" in refused(lambda: submit.prepare_arm(ghost)))
    case = submit.load_manifest(manifest("case.json", uci_options={"threads": 1, "MODE": "honest"}))
    check("option names match case-insensitively, as UCI specifies", not refused(lambda: submit.prepare_arm(case)))


def arm_with(mode, cert="none", **over):
    opts = {"Threads": 1, "Mode": mode, "Cert": cert}
    return submit.prepare_arm(submit.load_manifest(manifest("arm-%s-%s.json" % (mode, cert),
                                                            uci_options=opts, **over)))


def test_search():
    print("\nsearch and scoring")
    honest = arm_with("honest")
    rec = submit.search(honest["argv"], honest["options"], M2A, 2, "nodes 1000", 60)
    check("an honest mate in 2 is claimed as 2", rec["dm"] == 2 and rec["status"] == "ok", rec)
    rec = submit.search(honest["argv"], honest["options"], NOMATE, 3, "nodes 1000", 60)
    check("no claim where there is no mate", rec["dm"] is None and rec["status"] == "ok", rec)
    neg = arm_with("negative")
    rec = submit.search(neg["argv"], neg["options"], M2A, 2, "nodes 1000", 60)
    check("a negative mate score is not a solve", rec["dm"] is None, rec)
    over = arm_with("overlong")
    rec = submit.search(over["argv"], over["options"], M2A, 2, "nodes 1000", 60)
    check("a mate longer than asked for is not a solve", rec["dm"] is None, rec)
    eof = arm_with("eof")
    rec = submit.search(eof["argv"], eof["options"], M2A, 2, "nodes 1000", 60)
    check("an engine that exits before bestmove is recorded as such", rec["status"] == "exited before bestmove", rec)
    silent = arm_with("silent")
    rec = submit.search(silent["argv"], silent["options"], M1A, 1, "nodes 1000", 60)
    check("an engine's info strings are kept", "evaluation file not found" in rec["info"], rec)
    check("the positive control passes an honest engine", submit.positive_control(honest, "nodes 1000", 60) == "")
    problem = submit.positive_control(silent, "nodes 1000", 60)
    check("the positive control fails a silent engine, and says what it said",
          "positive control failed" in problem and "evaluation file not found" in problem, problem)


def cert_for(fen, n):
    ns = {}
    exec(SOLVER, ns)
    import chess
    return ns["certificate"](chess.Board(fen + " 0 1"), n)


def test_certificates():
    print("\ncertificates (checked by %s)" % certificates.checker().checker_path)
    big = 1 << 20
    good = json.dumps(cert_for(M2A, 2))
    check("a genuine mate-in-2 certificate is verified", certificates.verify(M2A, 2, good, big) == ("verified", ""))
    # Omit one defence from a defender node that has more than one, so what is
    # left is a real subset of the legal replies rather than an empty list.
    node = cert_for(M2WIDE, 2)
    stack, target = [node], None
    while stack and target is None:
        n = stack.pop()
        if len(n.get("d", [])) >= 2:
            target = n
        stack.extend(r["p"] for r in n.get("d", []))
    check("the test position has a defender node with two or more replies", target is not None)
    if target is not None:
        del target["d"][0]
        verdict, reason = certificates.verify(M2WIDE, 2, json.dumps(node), big)
        check("a certificate omitting a defence is rejected",
              verdict == "rejected" and "missing defences" in reason, reason)
    node = cert_for(M1A, 1)
    node["a"] = "d1d7"
    verdict, reason = certificates.verify(M1A, 1, json.dumps(node), big)
    check("a leaf that is not checkmate is rejected", verdict == "rejected" and "not checkmate" in reason, reason)
    node = cert_for(M2A, 2)
    node["d"] = []
    del node["d"][:]
    verdict, reason = certificates.verify(M2A, 2, json.dumps(node), big)
    check("an empty reply list is rejected", verdict == "rejected" and "empty reply list" in reason, reason)
    verdict, reason = certificates.verify(M2A, 3, good, big)
    check("a certificate shallower than the claim is rejected",
          verdict == "rejected" and "proves mate in 2, the claim is mate in 3" in reason, reason)
    verdict, reason = certificates.verify(M2B, 2, good, big)
    check("a certificate for another position is rejected", verdict == "rejected", reason)
    check("a certificate that is not JSON is rejected", certificates.verify(M2A, 2, "{oops}", big)[0] == "rejected")
    check("a certificate that is not an object is rejected", certificates.verify(M2A, 2, "[1, 2]", big)[0] == "rejected")
    node = cert_for(M2A, 2)
    del node["d"][0]["p"]
    verdict, reason = certificates.verify(M2A, 2, json.dumps(node), big)
    check("a reply without a sub-proof is rejected, not a crash", verdict == "rejected", reason)
    check("a certificate over the size limit is rejected",
          "over the" in certificates.verify(M2A, 2, good, 10)[1])
    check("no certificate is absent, not rejected", certificates.verify(M2A, 2, None, big) == ("absent", ""))
    line = "%s; acn 10; acs 0.0; bm x; dm 2; pv x; proof %s;" % (M2A, good)
    check("a MateProver result line yields its certificate", certificates.extract("noise\n" + line) == good)
    check("a bare JSON line yields its certificate", certificates.extract("noise\n" + good + "\n") == good)


def test_run_one():
    print("\ncertificate channels")
    big = 1 << 20
    arm = arm_with("honest", "valid", certificates={"channel": "info-string"})
    rec = submit.run_one(arm, M2A, 2, "nodes 1000", 60, big, str(TMP / "certs"))
    check("info-string: a genuine certificate is verified", rec["cert"] == "verified", rec)
    check("info-string: the certificate is kept when asked", any((TMP / "certs").rglob("*-dm2.json")))
    arm = arm_with("honest", "forged", certificates={"channel": "info-string"})
    rec = submit.run_one(arm, M2A, 2, "nodes 1000", 60, big, "")
    check("info-string: a forged certificate is rejected", rec["cert"] == "rejected", rec)
    arm = arm_with("honest", "garbage", certificates={"channel": "info-string"})
    rec = submit.run_one(arm, M2A, 2, "nodes 1000", 60, big, "")
    check("info-string: a garbled certificate is rejected", rec["cert"] == "rejected", rec)
    arm = arm_with("honest", "none", certificates={"channel": "command",
                                                   "argv": ["{engines}/mateprover", "--emit-proof", "-z", "{dm}", "-"]})
    rec = submit.run_one(arm, M2B, 2, "nodes 1000", 60, big, "")
    check("command: a certificate from a separate prover is verified", rec["cert"] == "verified", rec)
    arm = arm_with("honest", "none", certificates={"channel": "command", "argv": ["{engines}/fake"]})
    rec = submit.run_one(arm, M2B, 2, "nodes 1000", 60, big, "")
    check("command: a command that prints no certificate is absent, and says so",
          rec["cert"] == "absent" and "printed no certificate" in rec["cert_reason"], rec)
    arm = arm_with("honest")
    rec = submit.run_one(arm, M2B, 2, "nodes 1000", 60, big, "")
    check("an arm without certificates records none", rec["cert"] == "absent", rec)
    chatty = arm_with("silent")
    failed = submit.positive_control(chatty, "nodes 1000", 60)
    check("the positive control records the engine's baseline output on the arm it ran",
          failed != "" and chatty.get("baseline_info") == {"evaluation file not found"}, chatty.get("baseline_info"))


def corpus(name, rows):
    path = TMP / "corpora" / name
    path.write_text("".join("%s bm #%d; id \"t%d\";\n" % (f, d, i) for i, (f, d) in enumerate(rows)), encoding="utf-8")
    return path


def test_end_to_end():
    print("\nend to end")
    corpus("mini.epd", [(M1A, 1), (M1B, 1), (M2A, 2), (M2B, 2), (NOMATE, 3)])
    sub = manifest("sub.json", name="submission",
                   uci_options={"Threads": 1, "Mode": "honest", "Cert": "valid"},
                   certificates={"channel": "info-string"})
    ref = manifest("ref.json", name="reference", uci_options={"Threads": 1, "Mode": "honest", "Cert": "none"})
    state = str(TMP / "results" / "e2e_state.json")
    log = str(TMP / "results" / "e2e.log")
    args = [str(sub), "--against", str(ref), "--corpus", "mini.epd", "--min-depth", "1",
            "--nodes", "1000", "--jobs", "2", "--state", state, "--log", log]
    code, out = quiet(submit.main, args)
    check("a submission run completes", code == 0, out[-600:])
    text = Path(log).read_text(encoding="utf-8") if Path(log).exists() else ""
    row = lambda name: next((l.split() for l in text.splitlines() if l.strip().startswith(name + " ")), [])
    s, r = row("submission"), row("reference")
    # n claimed verified cert prover refuted unconfirmed error cert-fail no-end
    check("the submission's four mates are verified by its own certificates",
          s[1:7] == ["5", "4", "4", "4", "0", "0"], s)
    check("the reference's four mates are verified by MateProver", r[1:7] == ["5", "4", "4", "0", "4", "0"], r)
    check("the paired row shows no discordant pairs", any(l.split()[:7] == ["all", "5", "4", "4", "0", "0", "1.0000"]
                                                         for l in text.splitlines()), text[-800:])
    check("the log records options left at default", "at default  Cert=none, Hash=16" in text
          or "at default  Hash=16" in text, text[:1500])
    code, out = quiet(submit.main, args)
    check("a second run replays the checkpoint", "0 searches to run" in out and code == 0, out[:800])

    liar = manifest("liar.json", name="liar", uci_options={"Threads": 1, "Mode": "liar", "Cert": "none"})
    code, out = quiet(submit.main, [str(liar), "--corpus", "mini.epd", "--min-depth", "1", "--nodes", "1000",
                                    "--state", state, "--log", log])
    text = Path(log).read_text(encoding="utf-8")
    row_l = next((l.split() for l in text.splitlines() if l.strip().startswith("liar ")), [])
    check("false claims are refuted, true ones verified", row_l[1:7] == ["5", "5", "2", "0", "2", "3"], row_l)

    # Its own state file: the shared one holds MateProver verdicts for these same
    # claims, and replaying them is exactly what the checkpoint is for.
    os.environ["FAKE_PROVER"] = "timeout"
    try:
        slow = manifest("slow.json", name="slow", uci_options={"Threads": 1, "Mode": "honest", "Cert": "none", "Hash": 32})
        code, out = quiet(submit.main, [str(slow), "--corpus", "mini.epd", "--min-depth", "1", "--nodes", "1000",
                                        "--state", str(TMP / "results" / "slow_state.json"), "--log", log])
        text = Path(log).read_text(encoding="utf-8")
        row_s = next((l.split() for l in text.splitlines() if l.strip().startswith("slow ")), [])
        check("an exhausted verification budget is unconfirmed, not refuted",
              row_s[1:8] == ["5", "4", "0", "0", "0", "0", "4"], row_s)
    finally:
        os.environ.pop("FAKE_PROVER", None)

    corpus("tuned.epd", [(M1A, 1)])
    tuned = manifest("tuned.json", name="tuned", tuned_on=["tuned.epd"])
    code, out = quiet(submit.main, [str(tuned), "--against", str(ref), "--corpus", "mini.epd", "--min-depth", "1",
                                    "--nodes", "1000", "--state", state, "--log", log])
    check("positions an arm tuned on are dropped for every arm",
          "1 excluded: tuned declares tuning on tuned.epd" in out and "4 positions" in out, out[:1200])
    missing = manifest("missing.json", name="missing", tuned_on=["nowhere.epd"])
    code, out = quiet(submit.main, [str(missing), "--corpus", "mini.epd", "--min-depth", "1", "--nodes", "1000",
                                    "--state", state, "--log", log])
    check("a declared tuning corpus that is not present is refused", "cannot be excluded" in str(code), code)

    other = manifest("other.json", name="other", family="elsewhere")
    code, out = quiet(submit.main, [str(sub), "--against", str(other), "--corpus", "mini.epd", "--min-depth", "1",
                                    "--nodes", "1000", "--state", state, "--log", log])
    check("a node budget across families is refused", "different families" in str(code), code)
    code, out = quiet(submit.main, [str(sub), "--against", str(other), "--corpus", "mini.epd", "--min-depth", "1",
                                    "--movetime", "200", "--state", state, "--log", log])
    check("a clock budget across families runs", code == 0, out[-600:])

    silent = manifest("silent.json", name="silent", uci_options={"Threads": 1, "Mode": "silent"})
    code, out = quiet(submit.main, [str(silent), "--corpus", "mini.epd", "--min-depth", "1", "--nodes", "1000",
                                    "--state", state, "--log", log])
    check("a run whose engine fails the positive control is refused", "positive control failed" in str(code), code)


def test_lint():
    print("\nmeasurement lint")
    out = subprocess.run([sys.executable, str(HERE / "lint_measurement.py"), str(HERE / "submit.py"),
                          str(HERE / "certificates.py")], capture_output=True, text=True)
    check("submit.py and certificates.py pass the measurement lint", out.returncode == 0, out.stdout)


if __name__ == "__main__":
    certificates.checker()          # exits with instructions if MATEBENCH_MATEPROVER_REPO is wrong
    test_manifests()
    test_arms()
    test_search()
    test_certificates()
    test_run_one()
    test_end_to_end()
    test_lint()
    failed = [name for name, ok, _ in RESULTS if not ok]
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    for name in failed:
        print("  FAILED: %s" % name)
    sys.exit(1 if failed else 0)
