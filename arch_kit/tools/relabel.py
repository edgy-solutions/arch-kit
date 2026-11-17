#!/usr/bin/env python3
"""relabel.py - replace names in the decision records at export, leaving the sources alone.

A list file holds one rule per line: PATTERN<TAB>REPLACEMENT. Blank lines and lines
starting `#` are skipped. A pattern is a regular expression, compiled case-insensitively.
The list is supplied by the deployment; nothing in the repository names a value to replace.

apply() runs the rules in file order. Per match:
    a match of two or more letters, all uppercase, is replaced by the uppercased replacement;
    a match at the start of a sentence gets a replacement with a capital first letter;
    a replacement that starts with `the ` drops it when the word before the match is an
    article or a determiner (the, a, an, first, this, that, each, every).
A message about a bad line names the file and the line number, never the line.

apply_html() runs the same rules over a finished HTML document, segment by segment. A segment is a text run
between tags, or the value of a shown attribute (title, alt, aria-label, placeholder, content, data-title-*).
It never touches tag names, attribute names, id, href, class or any other attribute: those are structure, and a
name that reaches one is a leak for the render's scan to refuse, not something to rewrite. The contents of
<script>, <style> (an inline SVG's included) and comments are skipped whole.
    - Entities are matched as written: a rule for "a & b" does not match "a &amp; b" (a rule for a lone "&"
      still matches the "&" that starts "&amp;").
    - Inline SVG <text> and <tspan> content is a text run, so it is relabelled. The diagram was laid out for the
      original string, so a replacement of a different length can sit oddly; it is not re-rendered.
    - A rule cannot match across a tag: "alpha <b>beta</b>" is two runs.
    - Only quoted attribute values are rewritten.
Stdlib only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from data_exchange import InputError

DETERMINERS = {"the", "a", "an", "first", "this", "that", "each", "every"}
LEADING = re.compile(r"(?:\s|[#\-*>|`]|\d+\.(?=\s))*")
AFTER_STOP = re.compile(r"[.!?:]\s+(?:\*\*|`)?$")
WORD_BEFORE = re.compile(r"(\w+) +$")


class Rule(NamedTuple):
    pattern: re.Pattern
    replacement: str
    file: str
    line: int


def load(paths) -> list[Rule]:
    rules: list[Rule] = []
    for path in paths:
        name = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            raise InputError(f"relabel list {name} cannot be read") from None
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            pattern, tab, replacement = line.partition("\t")
            if not tab:
                raise InputError(f"relabel list {name} line {n} has no tab")
            try:
                rules.append(Rule(re.compile(pattern, re.IGNORECASE), replacement, name, n))
            except re.error:
                raise InputError(f"relabel list {name} line {n} does not compile") from None
    return rules


def sentence_start(prefix: str) -> bool:
    """The text before a match on its line: only markers, or a sentence stop."""
    return bool(LEADING.fullmatch(prefix) or AFTER_STOP.search(prefix))


def replacement_for(m: re.Match, replacement: str, block_start: bool | None = None) -> str:
    """The text for one match. block_start is set for a text run in HTML: whether a block tag opens it. The start
    of such a run is a sentence start only then; None keeps the rule for a whole text."""
    text = m.string
    prefix = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
    word = WORD_BEFORE.search(prefix)
    if replacement[:4].lower() == "the " and word and word.group(1).lower() in DETERMINERS:
        replacement = replacement[4:]
    letters = [c for c in m.group(0) if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return replacement.upper()
    if replacement and (block_start if block_start is not None and not text[:m.start()].strip() else sentence_start(prefix)):
        return replacement[0].upper() + replacement[1:]
    return replacement


def apply(text: str, rules) -> tuple[str, int]:
    total = 0
    for rule in rules:
        text, n = rule.pattern.subn(lambda m, r=rule.replacement: replacement_for(m, r), text)
        total += n
    return text, total


BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dt", "dd", "figcaption", "caption"}
SHOWN_ATTRS = {"title", "alt", "aria-label", "placeholder", "content"}
SKIPPED = re.compile(r"<!--.*?-->|<![^>]*>|<(script|style)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
TAG = re.compile(r"""<(/?)([a-zA-Z][^\s/>]*)((?:"[^"]*"|'[^']*'|[^>"'])*)>""")
ATTR = re.compile(r"""([^\s=/"'>]+)(\s*=\s*)("[^"]*"|'[^']*')""")


def _shown(name: str) -> bool:
    name = name.lower()
    return name in SHOWN_ATTRS or name.startswith("data-title-")


def _segment(text: str, rules, block_start: bool | None) -> tuple[str, int]:
    total = 0
    for rule in rules:
        text, n = rule.pattern.subn(
            lambda m, r=rule.replacement: replacement_for(m, r, block_start), text)
        total += n
    return text, total


def _tag(m: re.Match, rules) -> tuple[str, int]:
    total = 0

    def attr(a: re.Match) -> str:
        nonlocal total
        if not _shown(a.group(1)):
            return a.group(0)
        value, n = _segment(a.group(3)[1:-1], rules, None)
        total += n
        return a.group(1) + a.group(2) + a.group(3)[0] + value + a.group(3)[0]

    rest = ATTR.sub(attr, m.group(3))
    return f"<{m.group(1)}{m.group(2)}{rest}>", total


def apply_html(html: str, rules) -> tuple[str, int]:
    """The rules applied to a finished HTML document: text runs and shown attribute values only."""
    out: list[str] = []
    total = 0
    block = False  # the tag just before the run opens a block
    pos = 0
    for skip in list(SKIPPED.finditer(html)) + [None]:
        end = skip.start() if skip else len(html)
        chunk = html[pos:end]
        at = 0
        for t in TAG.finditer(chunk):
            run = chunk[at:t.start()]
            if run:
                run, n = _segment(run, rules, block)
                total += n
                out.append(run)
            tag, n = _tag(t, rules)
            total += n
            out.append(tag)
            block = not t.group(1) and t.group(2).lower() in BLOCKS
            at = t.end()
        run = chunk[at:]
        if run:
            run, n = _segment(run, rules, block)
            total += n
            out.append(run)
        if skip:
            out.append(skip.group(0))
            block = False
            pos = skip.end()
    return "".join(out), total


def survivors(text: str, rules) -> list[tuple[int, int, int]]:
    """(rule index, line number, matches) for every line of text a pattern still matches."""
    out = []
    for i, rule in enumerate(rules):
        for n, line in enumerate(text.split("\n"), 1):
            hits = len(rule.pattern.findall(line))
            if hits:
                out.append((i, n, hits))
    return out
