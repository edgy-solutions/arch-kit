"""The consumer's declared paths: where its architecture content, repository and decisions live.

The declaration is a YAML file named by env ARCH_KIT_CONFIG, or docs/arch/arch-kit.yaml under the
current directory. Paths in it are relative to the declaration file's own directory:

    kit: 1
    paths:
      root: .
      repo: ../..
      decisions: ../../decisions

ROOT, REPO and DECISIONS are the resolved paths; CONFIG is the parsed map. A missing file, a kit
version other than 1, or a missing path key exits 2 with a one-line message.

The other keys (name, model.file, model.package, exchange.annotations.produces and .groups,
exchange.schema_key, registers.follow_ups, .debt and .roadmap, readiness.default, loader) are optional at
load. need("model.file", "validate_sysml") returns the value when a tool uses it, and exits 2 with
`arch-kit: <decl path>: missing key 'model.file' (needed by validate_sysml)` when it is absent.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import yaml

KEYS = ("root", "repo", "decisions")


def _die(message):
    print(message, file=sys.stderr)
    raise SystemExit(2)


def die(message):
    """Exit 2 with a one-line message: a declaration that is present and wrong."""
    _die(message)


def _load():
    env = os.environ.get("ARCH_KIT_CONFIG")
    path = Path(env) if env else Path.cwd() / "docs" / "arch" / "arch-kit.yaml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        _die(f"arch-kit: {path}: declaration file not found or unreadable")
    except yaml.YAMLError:
        _die(f"arch-kit: {path}: not valid YAML")
    if not isinstance(config, dict) or config.get("kit") != 1:
        _die(f"arch-kit: {path}: key 'kit' must be 1")
    base = path.resolve().parent
    if config.get("portal") == "none":
        # A project with no portal of its own: it declares what it consumes, and needs no paths.
        if not config.get("consumes"):
            _die(f"arch-kit: {path}: portal: none needs consumes:")
        files = config.get("files")
        if isinstance(files, dict) and "composition" in files:
            _die(f"arch-kit: {path}: files.composition: a project with no portal composes nothing")
        if "paths" not in config:
            return config, {key: None for key in KEYS}, path
    paths = config.get("paths")
    if not isinstance(paths, dict):
        _die(f"arch-kit: {path}: missing key 'paths'")
    for key in KEYS:
        if key not in paths:
            _die(f"arch-kit: {path}: missing key 'paths.{key}'")
    return config, {key: (base / str(paths[key])).resolve() for key in KEYS}, path


CONFIG, _PATHS, PATH = _load()
ROOT = _PATHS["root"]
REPO = _PATHS["repo"]
DECISIONS = _PATHS["decisions"]


def require_portal(tool):
    """Exit 2 when the declaration says `portal: none`: that project has no portal for `tool` to check."""
    if CONFIG.get("portal") == "none":
        _die(f"arch-kit: {PATH}: portal: none: {tool} has no portal to check")


def need(dotted, tool):
    """The declared value at a dotted key, or exit 2 naming the key and the tool that needs it."""
    value = CONFIG
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            _die(f"arch-kit: {PATH}: missing key '{dotted}' (needed by {tool})")
        value = value[part]
    return value


_LOADERS: dict[str, object] = {}


def loader(tool):
    """The declared loader module (`loader:` in the declaration, relative to it), imported once by path.

    It reads the consumer's files and provides the names of arch_kit/tools/seam.py. A missing key
    exits 2 as need() does; a missing file exits 2 naming the path."""
    value = str(need("loader", tool))
    path = (PATH.resolve().parent / value).resolve()
    if str(path) not in _LOADERS:
        if not path.is_file():
            _die(f"arch-kit: {PATH}: loader file {path} not found")
        spec = importlib.util.spec_from_file_location("arch_kit_loader_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _LOADERS[str(path)] = module
    return _LOADERS[str(path)]


def model_file(tool, root=None):
    """The declared model file, resolved against root when given, else paths.root."""
    return (Path(root) if root else ROOT) / str(need("model.file", tool))


def readiness_default(chart_dir, tool):
    """The declared default readiness doc, relative to the chart directory."""
    return Path(os.path.normpath(Path(chart_dir) / str(need("readiness.default", tool))))
