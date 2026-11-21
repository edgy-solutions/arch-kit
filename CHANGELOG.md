# Changelog

## Unreleased

### Added

- **UAF Mi row.** The UAF grid places `Mi-` ids (Mission, UAF 1.3) in a Mi row between En and Me. The row is drawn
  only when Appendix A places an id in it, so a project with no `Mi-` id renders as before.
- **Connections and Protected by.** A component may carry `connections`: who it talks to (a component of the record,
  `<prefix>:CO-...` of a declared foreign member, or an outside system `XE-...`), the direction, protocol, sign-in,
  what passes, status and evidence. Each connection may carry `protected_by`, a list of `by` entries (a protecting
  component or outside system) and at most one `none` entry. A `none` entry is a known gap: it is reported on stderr
  as `components[i].connections[j].protected_by[k]: gap: none: <why>` and renders with a gap badge. A connection with
  no `protected_by` renders "not written" and is not reported. The Components page gains a Connections table, and
  `components.connection_rows`, `components.gaps` and `components.protected_by_cell` give the rows to other views.

## 0.3.1 (2026-11-19)

Long tokens in tables, and links to headings on declared pages.

### Changed

- **Break opportunities in long tokens.** In a table cell, a run of characters without whitespace gets `<wbr>` after `/ # ? & = _ - . :` and after every 20th character of a longer piece. The text, the escaping and the entities are unchanged. Inline code and an external link's printed target follow the same rule.
  - Columns 4 and later: runs of 24 or more characters.
  - Columns 1 to 3 hold ids and never wrap, so only runs longer than `ID_MAX` (47) get breaks there, such as a printed repository URL or a source path.
- **Header `min-width` counts a break hint as a break.** Before, a token split by `<wbr>` counted as one word and held its column at the token's full length.
- **Headings on declared pages get ids.** Each `h2` to `h4` gets `page-<id>--<slug>`, using GitHub's slug and its numbering of repeats. A link to a declared page's file, or to a heading on it, becomes an anchor. A bare fragment resolves against the page's own headings. A fragment with no heading links the page, and warns on stderr.

### Checks

- **The browser check's width rule.** The nine-column check is replaced by two rules:
  - the page doesn't scroll sideways at 1280;
  - every table wider than its container scrolls inside a `.scroll` whose `overflow-x` is `auto`.

  The optional `export.browser.expect_wide_table` makes `browser_facts` ask for at least one such table.
- **The mid-word check skips tokens longer than `id_max`.** It doesn't count them, and it reports how many there were as `long`. It fails when the facts carry no `id_max`. Facts written by an earlier `browser_facts` need regenerating.

## 0.3.0 (2026-11-19)

Composition, three record types, prose pages, and the full views export with no chart. Pull requests #21 and #23 to #27.

### Added

- **Composition** (#21), built as ruled on 2026-11-18:
  - a project that a portal composes is a *member*;
  - a consumer declares `consumes:`, and a project may declare `portal: none`;
  - the composition file, from which the decision index check takes its foreign prefixes;
  - the composed build: `render_html` and `check_export` with `files.composition` and `--checkout NAME=DIR`, with its lists, audience and pin states; and `portal.composed_in`.

  Before, the composed-build line sat under 0.2.0. It shipped in this release.
- **Flow records** (#23): one part sends one kind of record to another, over one channel, decided by named decisions.
  - Declared with `files.flows` or a loader's `load_flows(root)`. Ids are `FL-` followed by capitals, digits and hyphens.
  - They get a Flows page with counts and the flows no decision covers, lists on decision and capability pages, and a front-page entry.
  - In the composed build, each member's flows render with that member's pages.
- **The component record type** (#24): a part of the system, not a composed member.
  - Declared with `files.components` or `load_components(root)`, and the schema `arch_kit/schema/components.schema.json`.
  - A top-level `components:` map declares the planes.
- **The roadmap record type** (#25): the roadmap's order table as a checked record.
  - Declared with `files.roadmap` or `load_roadmap(root)`.
  - It takes the place of the roadmap note. Declaring both exits 2.
- **The prose page type** (#26): an overview and walkthroughs, declared with `files.pages` or `load_pages(root)`.
  - Every record a page cites must exist.
  - Every status a page claims must match the record's.
- **The full views export with no chart and no model** (#27).
  - `chart: none` refuses `--chart`, `--values` and `--release`. Slots, readiness and the declarations page aren't read.
  - Provenance has one `Source: NAME COMMIT` part per `--source NAME=COMMIT`, plus one `Kit: COMMIT` part.

## 0.2.0 (2026-11-18)

Decisions-only portals, the alignment record type, and the composition design as ruled.

### Added

- **The alignment record type** ([design](docs/design/alignment.md), proposed; built ahead of its ruling). A project declares `files.alignment`, a directory of records, or its loader defines `load_alignment(root)`. Records are validated against `arch_kit/schema/alignment.schema.json` and checked row by row. Each record gets a coverage page with counts, never a percentage, and the front page an "Alignment" list (`examples/alignment`). The first seed is the NATO Data Centric Reference Architecture, Version 2: ids, names and section citations only. A public portal refuses a reference with restricted terms, and one with unconfirmed terms that carries elements.
- **The composition design** ([design](docs/design/composition.md)), ruled on 2026-11-18. A project a portal composes is a *member* of it. Nothing of it is built in this release.

### Changed

- A decision-page table renders when the project declares no `labels.*` keys. Before, it exited 2. View tables are unchanged.

### Breaking

- A decision record file must now be named `PREFIX-<digits>-<slug>.md` (or `<digits>-<slug>.md` with `file_prefix: false`), with exactly the declared number of digits and a slug of at least one character. Before, any file matching `PREFIX-*.md` counted as a record (for example `ADR-0045.md`, `ADR-45-title.md` or `ADR-draft.md`). The checks and the render now ignore a file whose name has no slug or the wrong digit count, so its page and its checks vanish without an error. Rename each such file to the full form, for example `ADR-0045.md` to `ADR-0045-<slug>.md` and `ADR-45-title.md` to `ADR-0045-title.md`.

### Declaration keys

New optional declaration keys for what 0.1.0 fixed. Every default is the 0.1.0 value, so an existing declaration's
output is unchanged, with one exception: the record file name is now checked more strictly (see Breaking).

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
