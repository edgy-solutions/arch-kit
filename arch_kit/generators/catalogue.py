"""The view catalogue: the views a loader can present, in `views.yaml`, and the checks a loader's own copy must pass.

A loader reads the catalogue with `load()`, may replace fields of a view by key with `merge()`, and checks the result
with `check()`. Every error is a `CatalogueError` whose text starts with the label the caller gives.
"""
from __future__ import annotations

from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parent / "views.yaml"
GENERATORS = ("overview", "traceability", "correspondence", "services", "standards", "roadmap",
              "resources", "structure", "connectivity", "sequences-parts", "sequences-roles",
              "security-structure", "security-connectivity", "security-processes",
              "strategic-taxonomy", "services-traceability")
STATUSES = ("feeds", "fields", "none")


class CatalogueError(Exception):
    pass


def load(label: str = "catalogue") -> dict:
    """The packaged catalogue as {"groups": [...], "views": [...]}, checked."""
    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    out = {"groups": data["groups"], "views": data["views"]}
    check(out["groups"], out["views"], label)
    return out


def merge(catalogue: dict, overrides, label: str = "catalogue") -> dict:
    """A copy of the catalogue with each override's fields set on the view of that key. An override of a key the
    catalogue does not hold is an error; so is an override that is not a map of maps."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict) or not all(isinstance(f, dict) for f in overrides.values()):
        raise CatalogueError(f"{label}: overrides must be a map of view key to fields")
    keys = {v["key"] for v in catalogue["views"] if isinstance(v, dict) and "key" in v}
    for key in overrides:
        if key not in keys:
            raise CatalogueError(f"{label}: overrides.{key}: names a view not in the catalogue")
    views = [{**v, **overrides.get(v.get("key"), {})} if isinstance(v, dict) else v for v in catalogue["views"]]
    return {"groups": catalogue["groups"], "views": views}


def check(groups, views, label: str = "catalogue") -> None:
    """Raises CatalogueError when the groups or the views are malformed."""
    if not isinstance(groups, list) or not all(isinstance(g, dict) and "key" in g and "title" in g for g in groups):
        raise CatalogueError(f"{label}: groups must be a list of key and title")
    if not isinstance(views, list):
        raise CatalogueError(f"{label}: views must be a list")
    group_keys = {g["key"] for g in groups}
    seen = set()
    for i, v in enumerate(views):
        if not isinstance(v, dict) or not isinstance(v.get("key"), str) or not v["key"]:
            raise CatalogueError(f"{label}: views[{i}].key: a view needs a key")
        key = v["key"]
        if key in seen:
            raise CatalogueError(f"{label}: views[{i}].key: duplicate view key {key}")
        seen.add(key)
        if not isinstance(v.get("title"), str) or not v["title"]:
            raise CatalogueError(f"{label}: views[{i}].title: {key} needs a title")
        if v.get("group") not in group_keys:
            raise CatalogueError(f"{label}: views[{i}].group: {key} names a group not in groups")
        if v.get("status") not in STATUSES:
            raise CatalogueError(f"{label}: views[{i}].status: {key} must be feeds, fields or none")
        gen = v.get("generator")
        if gen is not None and gen not in GENERATORS:
            raise CatalogueError(f"{label}: views[{i}].generator: {key} names an unknown generator")
        if v["status"] == "feeds" and gen is None:
            raise CatalogueError(f"{label}: views[{i}].generator: {key} is feeds and has no generator")
