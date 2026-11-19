"""The seam between the kit's rules and the consumer's files.

The kit reads none of the consumer's files. The consumer declares a loader module (`loader:` in
arch-kit.yaml, relative to the declaration) that provides the names below, and the kit calls them
through project.loader(tool). The record comes back in the neutral shape, which
arch_kit/schema/record.schema.json describes:

    groups, environments, entries (each with `environment`), capabilities (each with `degraded_mode`)

The consumer's own file may spell those keys differently; mapping them is the loader's job.
Signatures are the ones the kit's tools call.

One more name is optional: `load_alignment(root)`, for a project that keeps its alignment records (see
docs/design/alignment.md) somewhere other than `files.alignment`. A loader may leave it out; it is not in NAMES.
Another is `load_components(root)`, for a project that keeps its component records somewhere other than
`files.components`; it returns a list of components and is optional in the same way.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Protocol


class Loader(Protocol):
    KEY_NAMES: dict[str, str]  # each neutral key to the consumer's own, printed in the kit's messages

    def load_record(self, path) -> dict:
        """The record in the neutral shape; raises InputError when the file cannot be read or is not one."""

    def model_capabilities(self, sysml_text: str) -> dict[str, str]:
        """Concrete capability name to its direct parent, in model order."""

    def read_text(self, path: Path) -> str | None:
        """The file's text, or None when it cannot be read."""

    def adr_file(self, decisions_dir: Path, adr: str) -> Path | None:
        """The one decision record file for an ADR id, or None when there is not exactly one."""

    def adr_lead(self, decisions_dir: Path, adr: str) -> str | None:
        """The record's status, lowercased and trimmed; None when there is no file or no status."""

    def adr_status(self, text: str) -> str | None:
        """The status a decision record's text states, or None."""

    def register_rows(self, text: str) -> dict[str, str]:
        """Row id to status, for every register table in the text."""

    def register_subjects(self, text: str) -> dict[str, tuple[str, str]]:
        """Row id to (subject, status), for every register table in the text."""

    def roadmap_rows(self, text: str) -> list[list[str]]:
        """The roadmap's table rows, each a list of cells."""

    def index_status(self, index_text: str, adr: str) -> str | None:
        """The status the decisions index gives an ADR (accepted or proposed), or None."""

    def resolve_entries(self, record: dict, readiness_lines: list[str]) -> tuple[dict, list[str]]:
        """Entry name to (anchor line index, date, section), and the failures."""

    def quote_of(self, lines: list[str], at: int) -> str:
        """The cited readiness line, as a short quote."""

    def measured_line(self, readiness_lines: list[str], at: int, text: str) -> list[int]:
        """Indexes of the readiness lines holding text, from the anchor to the next heading."""

    def resolve_quotes(self, record: dict, readiness: list[str], entries: dict | None = None) -> tuple[dict, list[str]]:
        """(capability, index of its measured citation) to the cited readiness quote, and the failures."""

    def load_alignment(self, root: Path) -> dict[str, dict]:
        """Optional. Record name to alignment record, in the kit's shape; root is paths.root."""

    def load_components(self, root: Path) -> list[dict]:
        """Optional. The component records, in the kit's shape; root is paths.root."""


# Names a loader may leave out.
OPTIONAL_NAMES = ("load_alignment", "load_components")

# Every name a loader must provide: KEY_NAMES and each function above, less the optional ones.
NAMES = ("KEY_NAMES", *(n for n, v in vars(Loader).items()
                        if inspect.isfunction(v) and not n.startswith("_") and n not in OPTIONAL_NAMES))


# Under `portal.mode: decisions` the kit reads no capability record, so a loader needs only the decision functions.
# The capability functions are the record's loading and the readiness quotes; KEY_NAMES is for the record's messages.
CAPABILITY_NAMES = ("KEY_NAMES", "load_record", "model_capabilities", "resolve_entries", "quote_of", "measured_line",
                    "resolve_quotes")
DECISION_NAMES = tuple(n for n in NAMES if n not in CAPABILITY_NAMES)


def names_for(mode: str) -> tuple:
    """The names a loader must provide under a portal mode: every name for `full`, the decision names for `decisions`."""
    return DECISION_NAMES if mode == "decisions" else NAMES
