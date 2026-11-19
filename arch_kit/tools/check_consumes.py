#!/usr/bin/env python3
"""check_consumes.py - check this project's own `consumes:` entries, against local clones of the consumed projects.

Usage:
    python -m arch_kit check_consumes [--checkout NAME=DIR[:DECL]] ...

NAME is a consumed project's name (`consumes[].portal`), DIR a local clone of it, and DECL the path of that
project's declaration inside the clone (default docs/arch/arch-kit.yaml). For each entry with a checkout the tool
asks git whether the pinned commit exists, reads the consumed declaration at the pin, and checks that each decision
record the entry names exists at the pin, under the CONSUMED project's own record grammar. It never imports the
consumed project's code. A `capability:` reference is left to the composed build. An entry with no checkout is
printed as not checked, and the summary counts it as not checked: that is not a pass.

Exit codes: 0 no failure (entries not checked do not fail), 1 one or more failures, 2 input.
"""
from __future__ import annotations

import argparse
import posixpath
import subprocess
import sys

import yaml

import declared
import project

TOOL = "check_consumes"
DEFAULT_DECL = declared.DEFAULT_DECLARATION


class _Refused(Exception):
    pass


def _git(directory, *args):
    p = subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


def _refuse(key, why):
    raise _Refused(f"{key}: {why}")


def _record_names(directory, commit, decl, text):
    """(set of record ids at the commit, None) from the consumed declaration's text, or (None, why)."""
    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, f"{decl} is not valid YAML"
    if not isinstance(config, dict) or config.get("kit") != 1:
        return None, f"{decl}: key 'kit' must be 1"
    paths = config.get("paths")
    if not isinstance(paths, dict) or not isinstance(paths.get("decisions"), str):
        return None, f"{decl}: missing key 'paths.decisions'"
    try:
        prefix, digits, file_prefix = declared.record_grammar(config, _refuse)
    except _Refused as e:
        return None, f"{decl}: {e}"
    folder = posixpath.normpath(posixpath.join(posixpath.dirname(decl), paths["decisions"].replace("\\", "/")))
    if folder == ".." or folder.startswith("../") or folder.startswith("/"):
        return None, f"{decl}: paths.decisions {paths['decisions']!r} is outside the repository"
    args = ["ls-tree", "--full-tree", "--name-only", commit]
    if folder != ".":
        args += ["--", folder + "/"]
    code, out = _git(directory, *args)
    if code != 0:
        return None, f"cannot list {folder} at the pin"
    import re
    regex = declared.record_file_regex(prefix, digits, file_prefix)[0]
    ids = set()
    for line in out.splitlines():
        m = re.fullmatch(regex, posixpath.basename(line))
        if m:
            ids.add(f"{prefix}-{m.group('n')}")
    return ids, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check this project's consumes: entries against local clones.")
    ap.add_argument("--checkout", action="append", default=[], metavar="NAME=DIR[:DECL]",
                    help="a local clone of a consumed project, and the path of its declaration inside it")
    a = ap.parse_args(argv)
    entries = declared.consumes(TOOL)
    if not entries:
        print("check_consumes: no consumes: declared")
        return 0
    checkouts = {}
    for item in a.checkout:
        name, eq, rest = item.partition("=")
        if not eq or not name or not rest:
            project.die(f"arch-kit: {TOOL}: --checkout {item!r} is not NAME=DIR[:DECL]")
        directory, decl = rest, DEFAULT_DECL
        # DECL follows the last colon, unless that colon is a drive letter's (C:/...).
        head, colon, tail = rest.rpartition(":")
        if colon and head and not (len(head) == 1 and head.isalpha() and tail[:1] in ("/", "\\")) and tail:
            directory, decl = head, tail
        if name not in [e.portal for e in entries]:
            project.die(f"arch-kit: {TOOL}: --checkout {name}: no consumes: entry names {name!r}")
        checkouts[name] = (directory, decl)
    checked = unchecked = failed = 0
    for i, e in enumerate(entries):
        label = f"consumes[{i}]: {e.portal}"
        if e.portal not in checkouts:
            print(f"{label}: not checked: no checkout given")
            unchecked += 1
            continue
        directory, decl = checkouts[e.portal]
        short = e.commit[:7]
        code, _ = _git(directory, "cat-file", "-e", e.commit + "^{commit}")
        if code != 0:
            print(f"{label}: pin not found: {short}")
            failed += 1
            continue
        code, text = _git(directory, "show", f"{e.commit}:{decl}")
        if code != 0:
            print(f"{label}: declaration {decl} not found at {short}")
            failed += 1
            continue
        ids, why = _record_names(directory, e.commit, decl, text)
        if ids is None:
            print(f"{label}: {why}")
            failed += 1
            continue
        bad = False
        for ref in e.records or ():
            if ref.startswith("capability:"):
                print(f"{label}: {ref}: checked when composed")
            elif ref not in ids:
                print(f"{label}: {ref} not found at {short}")
                bad = True
        if bad:
            failed += 1
        else:
            checked += 1
    print(f"check_consumes: {len(entries)} entries: {checked} checked, {unchecked} not checked, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
