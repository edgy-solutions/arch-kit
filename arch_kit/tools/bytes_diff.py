"""Compare two builds as bytes, and say where they first differ. Used by the tests that build twice."""
from __future__ import annotations

import difflib
from pathlib import Path


def same_bytes_message(a: Path, b: Path) -> str | None:
    """None when the two files hold the same bytes; otherwise a message that shows where they first differ."""
    x, y = a.read_bytes(), b.read_bytes()
    if x == y:
        return None
    n = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), min(len(x), len(y)))
    start = max(0, n - 60)

    def window(data: bytes) -> str:
        return data[start:start + 200].decode("utf-8", errors="replace")

    diff = list(difflib.unified_diff(x.decode("utf-8", errors="replace").split("\n"),
                                     y.decode("utf-8", errors="replace").split("\n"),
                                     "first", "second", lineterm="", n=0))
    return (f"two builds wrote different bytes: sizes {len(x)} and {len(y)}; first difference at offset {n}\n"
            f"first, from offset {start}:\n{window(x)!r}\nsecond, from offset {start}:\n{window(y)!r}\n"
            "unified diff, first 40 lines:\n" + "\n".join(diff[:40]))
