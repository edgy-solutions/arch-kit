# Changelog

## Unreleased

New optional declaration keys for what 0.1.0 fixed. Every default is the 0.1.0 value, so an existing declaration's
output is unchanged, with one exception: the record file name is now checked more strictly (see Breaking).

### Added

- Composed build: `render_html` and `check_export` with `files.composition` and `--checkout NAME=DIR`; `portal.composed_in`.

### Breaking

- A decision record file must now be named `PREFIX-<digits>-<slug>.md` (or `<digits>-<slug>.md` with `file_prefix: false`), with exactly the declared number of digits and a slug of at least one character. Before, any file matching `PREFIX-*.md` counted as a record (for example `ADR-0045.md`, `ADR-45-title.md` or `ADR-draft.md`). The checks and the render now ignore a file whose name has no slug or the wrong digit count, so its page and its checks vanish without an error. Rename each such file to the full form, for example `ADR-0045.md` to `ADR-0045-<slug>.md` and `ADR-45-title.md` to `ADR-0045-title.md`.

- `files.*`: the content file names (`profiles`, `slots`, `appendix`, `inventory`, `readme`, `record`, `adr_exemptions`, `annotation_exceptions`).
- `decisions.index.readme` is also read by `capability_phases` when the other `decisions.index` keys are absent.
- `decisions.records.prefix` and `.digits`: the decision record id and file name.
- `decisions.records.file_prefix`: false names a record file `<digits>-<slug>.md`; the record id keeps its prefix.
- `portal.mode`: `decisions` makes a portal of the decision records, their index and the roadmap note, with no capability record, views or model (`examples/decisions-only`). The default is `full`.
- `decisions.index.register: none`: a decisions-only project declares that it has no register. Checks 1, 3 and 4 of `check_decision_indexes` do not run, and the run says so; a missing `register` key still exits 2, and `none` in full mode exits 2.
- `decisions.index.register_id.letters` and `.digits`: the register id grammar of `check_decision_indexes`.
- `derived.roadmap.increments` and `.fold_ins`: the roadmap note's table headers.

## 0.1.0 (2026-11-17)

The first release. Each step of Phase 1 in a sentence:

- **Step 1:** the tools moved out of the first project unchanged, and read the content paths from the project's declaration.
- **Step 2:** no project names in the kit; names, keys and file names are declared, and a test fails on a name that leaks back in.
- **Step 3:** a loader seam, so each project reads its own files into a neutral record the kit checks against a JSON Schema; labels, phases, statuses and view kinds are declared.
- **Step 4:** relabelling and the leak scan run on the rendered HTML, and a leak writes no file.
- **Step 5:** each portal declares its hosting and its audience, and a public audience requires the relabel and barred lists.
- **Step 6a:** the decision-index check moved into the kit, with its names declared in `decisions.index`.
- **Step 6b:** the `arch-kit` command, a declared term dictionary, an optional declared data exchange, and the minimal example project with its self-test.
- **Step 6c:** a composite GitHub Action that runs the whole chain, uploads the export when the portal declares `ci-artifact`, and a `portal` subcommand that prints the declaration.
- **Step 6d:** `check_views --record FILE` checks a project's own capability record in place of the default, and the phases view names that record in plain words when the render uses one.
