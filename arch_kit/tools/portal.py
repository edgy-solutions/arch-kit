#!/usr/bin/env python3
"""portal.py - print the portal declaration, for the Action.

Usage:
    python -m arch_kit portal

With `--mode` it prints only `portal.mode` (`full` when the key is absent). Otherwise it prints `HOSTING AUDIENCE` on one line, for example `ci-artifact public`, read from `portal.hosting` and
`portal.audience` through declared.py. Exit 2, naming the key, when the declaration or either value is bad.
"""
from __future__ import annotations

import sys

import declared


def main() -> int:
    if sys.argv[1:] == ["--mode"]:
        print(declared.portal_mode("portal"))
        return 0
    print(declared.portal_hosting("portal"), declared.portal_audience("portal"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
