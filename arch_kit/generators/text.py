"""Markdown text helpers the generators use: links to records, table cells, tables and fences."""
from __future__ import annotations

import html as H
import posixpath
import re
from urllib.parse import unquote

FENCE = re.compile(r"^\s*(```|~~~)")


CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")


INLINE_LINK = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")


REF_DEF = re.compile(r"^(\s{0,3}\[[^\]]+\]:\s*)(\S+)(.*)$")


ABSOLUTE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


RECORDS_FROM_VIEW = "../pages/records.md"


def link_path(href: str, base: str):
    """The repo path a relative markdown link points at, or None for an absolute, fragment or empty one."""
    href = H.unescape(href).strip()
    if href.startswith("<") and href.endswith(">"):
        href = href[1:-1]
    if ABSOLUTE.match(href) or href.startswith(("//", "#")):
        return None
    target = unquote(re.split(r"[#?]", href)[0])
    if not target:
        return None
    return posixpath.normpath(posixpath.join(base, target))


def rec_link(rec, prefix, label=None) -> str:
    """A link to the record on the records page, `<page file>#<slug of its heading>`; text when it has no heading.
    A record with `href` set links there instead."""
    text = (label or rec.display_id).replace("[", "(").replace("]", ")")
    if rec.href:
        return f"[{text}]({rec.href})"
    return f"[{text}]({prefix}#{rec.anchor})" if rec.anchor else text


def rewrite_links(line: str, base: str, path_map: dict, prefix: str) -> str:
    def sub(m):
        bang, text, href = m.group(1), m.group(2), m.group(3)
        if bang:
            return text
        full = link_path(href, base)
        anchor = path_map.get(full) if full else None
        return f"[{text}]({prefix}#{anchor})" if anchor else text

    parts, at = [], 0
    for c in CODE_SPAN.finditer(line):
        parts.append(INLINE_LINK.sub(sub, line[at:c.start()]))
        parts.append(c.group(0))
        at = c.end()
    parts.append(INLINE_LINK.sub(sub, line[at:]))
    return "".join(parts)


def cell(text, rec=None, path_map=None, prefix=RECORDS_FROM_VIEW) -> str:
    """Text for one table cell: links rewritten when the record is known, pipes escaped, one line."""
    text = "" if text is None else str(text)
    if rec is not None:
        text = rewrite_links(" ".join(text.split()), posixpath.dirname(rec.path), path_map or {}, prefix)
    text = " ".join(text.split())
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def table(headers, rows) -> str:
    """Headers and cells are markdown, already made one line with their pipes escaped."""
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out) + "\n"


def fence(lang: str, text: str) -> str:
    return f"```{lang}\n{text.rstrip(chr(10))}\n```\n"


def linked_paths(rec) -> set:
    """The repo paths the record's markdown links resolve to, by the same resolution as `body`."""
    base = posixpath.dirname(rec.path)
    out, fenced = set(), False
    for ln in rec.text.split("\n"):
        if FENCE.match(ln):
            fenced = not fenced
            continue
        if fenced:
            continue
        stripped = CODE_SPAN.sub("", ln)
        for m in INLINE_LINK.finditer(stripped):
            full = link_path(m.group(3), base)
            if full and not m.group(1):
                out.add(full)
        d = REF_DEF.match(stripped)
        if d:
            full = link_path(d.group(2), base)
            if full:
                out.add(full)
    return out
