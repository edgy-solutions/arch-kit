#!/usr/bin/env python3
"""check_views_canary.py - prove the `quotes` and `floor` rules can fail.

A rule that has never failed is not known to work. This copies the architecture root,
the declared decisions directory, the declared dictionary directory and .github (when it exists) to a temp directory (same relative layout), breaks the copy one way
per case, runs check_views.py on it as a subprocess, and compares the exit
code and a required fragment of stderr.

Takes the same five inputs as check_views.py. Prints only case names and pass
or fail; on a fail, the expected and actual exit code and the rule prefix. It
never prints what the child wrote, and never prints the word the quotes case
plants.

Exit codes: 0 every case behaved, 1 a case did not, 2 bad input. Stdlib and
PyYAML only.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

import capability_phases
import declared
import project

HERE = Path(__file__).resolve().parent
ARCH = project.ROOT
REPO = project.REPO
TOOL = HERE / "check_views.py"
EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2


def edit_record(root: Path, change) -> None:
    """Load the copied record, apply change(record), dump it back."""
    p = root / declared.content_file("record", "check_views_canary")
    record = yaml.safe_load(p.read_text(encoding="utf-8"))
    change(record)
    p.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")


def drop_built(record: dict) -> None:
    del record["capabilities"]["ArrivalDeclaration"]["built"]


def drop_first_workload_claim(record: dict) -> None:
    claims = record["rendered"]["workload"]
    del claims[next(iter(claims))]


def plant_word(a: argparse.Namespace, clean_output: str) -> str:
    """A literal word from the first evidence cell of the real render, safe to look for in output."""
    record = capability_phases.load_record(ARCH / declared.content_file("record", "check_views_canary"))
    cells = capability_phases.evidence_cells(record, Path(a.readiness).read_text(encoding="utf-8"))
    first = next((c[0] for c in cells.values() if c), None)
    if not first:
        raise capability_phases.CheckError("no capability in the real record has an evidence cell")
    # The child's output names capabilities, "the record" and its own wording; the word must not be in those.
    names = " ".join(record["capabilities"]).lower() + " the record quotes carries barred value ok rules views fail"
    for word in re.findall(r"[A-Za-z]{5,}", first):
        if word.lower() not in names and word.lower() not in clean_output.lower():
            return word
    raise capability_phases.CheckError("no word in the first evidence cell can be told apart from the output")


def main(argv: list[str] | None = None) -> int:
    project.require_portal("check_views_canary")
    ap = argparse.ArgumentParser(description="Prove check_views' quotes and floor rules can fail.")
    ap.add_argument("--chart", required=True)
    ap.add_argument("--values", action="append", default=[], required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--readiness", required=True)
    ap.add_argument("--barred", action="append", default=[], required=True)
    a = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp())
    try:
        return run_cases(a, tmp)
    finally:
        shutil.rmtree(tmp, True)


def run_cases(a: argparse.Namespace, tmp: Path) -> int:
    ignore = shutil.ignore_patterns("__pycache__", "out", "node_modules")
    # The copy keeps the repository's own layout, so the copy's declaration resolves the same relative paths.
    rel = lambda p: Path(os.path.relpath(p, REPO))  # noqa: E731
    arch_rel, dec_rel = rel(ARCH), rel(project.DECISIONS)
    dict_rel = Path(declared.dictionary("check_views_canary").dir)
    shutil.copytree(ARCH, tmp / arch_rel, ignore=ignore)
    shutil.copytree(project.DECISIONS, tmp / dec_rel)
    extra = [dict_rel] + ([Path(".github")] if (REPO / ".github").is_dir() else [])  # the README links to the workflows
    for part in extra:
        shutil.copytree(REPO / part, tmp / part)  # Am-If's table is built from the dictionary directory
    clean = tmp / arch_rel
    pristine = tmp / "pristine"
    for part in [arch_rel, dec_rel, *extra]:
        shutil.copytree(tmp / part, pristine / part)

    def flags(barred: list[str]) -> list[str]:
        out = ["--chart", a.chart, "--release", a.release, "--readiness", a.readiness]
        for v in a.values:
            out += ["--values", v]
        for b in barred:
            out += ["--barred", b]
        return out

    def run(root: Path, barred: list[str]) -> tuple[int, str]:
        env = {**os.environ, "ARCH_KIT_CONFIG": str(root / "arch-kit.yaml")}  # the copy's own declaration
        p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), *flags(barred)],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        return p.returncode, p.stdout + p.stderr

    cases = []  # (name, root, barred, expected exit, fragment in stderr, word that must not appear)
    cases.append(("clean", clean, a.barred, EXIT_OK, "", None))

    floor = tmp / "floor"
    shutil.copytree(pristine, floor)
    edit_record(floor / arch_rel, drop_built)
    cases.append(("floor", floor / arch_rel, a.barred, EXIT_CHECK, "floor: ArrivalDeclaration", None))

    unclaimed = tmp / "unclaimed"
    shutil.copytree(pristine, unclaimed)
    edit_record(unclaimed / arch_rel, drop_first_workload_claim)
    cases.append(("unclaimed", unclaimed / arch_rel, a.barred, EXIT_CHECK, "does not claim it", None))

    rc0, out0 = run(clean, a.barred)
    try:
        word = plant_word(a, out0)
    except (capability_phases.CheckError, capability_phases.InputError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    planted = tmp / "planted.txt"
    planted.write_text(word + "\n", encoding="utf-8", newline="\n")
    cases.append(("quotes", clean, [str(planted)], EXIT_CHECK, "quotes: ", word))

    empty = tmp / "empty.txt"
    empty.write_text("", encoding="utf-8")
    cases.append(("empty list", clean, [str(empty)], EXIT_INPUT, "", None))

    bad = 0
    for name, root, barred, want, fragment, secret in cases:
        rc, out = run(root, barred)
        problems = []
        if rc != want:
            problems.append(f"expected exit {want}, got {rc}")
        if fragment and fragment not in out:
            problems.append(f"rule prefix {fragment!r} not in the output")
        if secret and secret.lower() in out.lower():
            problems.append("the planted word is in the output")
        if problems:
            bad += 1
        print(f"{name}: {'FAIL (' + '; '.join(problems) + ')' if problems else 'pass'}")
    return EXIT_CHECK if bad else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
