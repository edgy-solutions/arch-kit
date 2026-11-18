#!/usr/bin/env python3
"""check_decision_indexes.py - the decision index checks, with every name declared.

Usage:
    python -m arch_kit check_decision_indexes

Reads `decisions.index` from the declaration, exports the names to check_decision_indexes.sh, and runs it with
bash from the declared decisions directory. The script's stdout, stderr and exit code are passed through
unchanged. Set PINS_OUT to a file to receive the list of pins that each foreign pin check printed.

The four checks and what they do not prove are in docs/rules.md. Exit codes: 0 clean, 1 drift, 2 input (a missing or
invalid declaration, a missing directory or pin check, or no bash on the PATH; the message names the key).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import declared
import project

TOOL = "check_decision_indexes"
SCRIPT = Path(__file__).resolve().with_suffix(".sh")


def _rel(path: Path, start: Path) -> str:
    return os.path.relpath(path, start).replace(os.sep, "/")


def main() -> int:
    index = declared.decisions_index(TOOL)
    directory, repo = project.DECISIONS, project.REPO
    if not directory.is_dir():
        project.die(f"arch-kit: {project.PATH}: paths.decisions: {directory} is not a directory")
    foreign = []
    for i, entry in enumerate(index.foreign):
        pin = ""
        if entry.pin_check is not None:
            path = repo / entry.pin_check
            if not path.is_file():
                project.die(f"arch-kit: {project.PATH}: decisions.index.foreign[{i}].pin_check: "
                            f"{path} is not a file")
            pin = _rel(path, directory)
        foreign.append(f"{entry.prefix}\t{pin}")
    bash = shutil.which("bash")
    if bash is None:
        project.die(f"arch-kit: {TOOL} needs bash on the PATH")
    env = dict(os.environ,
               IDX_DIRNAME=directory.name, IDX_REGISTER=index.register, IDX_README=index.readme,
               IDX_HOMES=" ".join(index.register_homes), IDX_INDEXED=" ".join(index.indexed),
               IDX_LOCAL=index.local_prefix, IDX_FOREIGN="\n".join(foreign), IDX_ROOT=_rel(repo, directory))
    sys.stdout.flush()
    sys.stderr.flush()
    return subprocess.run([bash, str(SCRIPT)], cwd=directory, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
