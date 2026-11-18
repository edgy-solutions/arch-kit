#!/usr/bin/env python3
"""portal.py - print the portal declaration, for the Action.

Usage:
    python -m arch_kit portal

Prints `HOSTING AUDIENCE` on one line, for example `ci-artifact public`, read from `portal.hosting` and
`portal.audience` through declared.py. Exit 2, naming the key, when the declaration or either value is bad.
"""
from __future__ import annotations

import declared


def main() -> int:
    print(declared.portal_hosting("portal"), declared.portal_audience("portal"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
