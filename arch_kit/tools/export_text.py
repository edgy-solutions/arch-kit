"""export_text.py - the text of an HTML export, read the same way by the render's leak scan and by check_export.

Stdlib only.
"""
from __future__ import annotations

import html
import re


def plain(raw: str) -> str:
    """Text with tags stripped, entities unescaped and whitespace collapsed to one space."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", raw))).strip()


def spaced(raw: str) -> str:
    """Text with each tag read as a space, entities unescaped and whitespace collapsed to one space."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", raw)))


def barred_strings(raw: str) -> list[str]:
    """The strings a barred value is scanned in: the raw file, its text, its spaced text, its text without spaces."""
    text = plain(raw)
    return [raw, text, spaced(raw), re.sub(r"\s+", "", text)]


def unescaped(raw: str) -> str:
    """The raw file with entities unescaped, tags kept: the second string a relabel survivor is scanned in."""
    return html.unescape(raw)
