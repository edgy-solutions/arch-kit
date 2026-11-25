# Changelog

## Unreleased

### Added

- View generators over neutral records, and the view catalogue, for a consuming project's loader to call.
- `arch_kit.generators.records.parse`, which reads a markdown record into a `Record`.
- The Security Structure view reads a grants table, `# | role | granted to | grants | granted by | status`, then
  evidence, under a "security roles" heading in a record of any kind. It shows each grant as written, with a
  sentence counting grants, roles and statuses. There's no "how closely" count and no gap list, because a grant
  isn't a correspondence to a reference. The correspondence table is read and shown as before.
- `check_views` checks, when `decisions.accounted_for` is declared, that every decision record of the named
  statuses is either cited by a capability or listed as untraced by decision. An untraced entry says
  `capability: none, by decision`, names the record that decided it, and gives one line of reason. A record in
  neither place, or in both, fails. Without the key, nothing changes.

## 0.4.1 (2026-11-21)

A full-mode project may declare that it has no decision register, and the README says what `check_views`
checks against a deployment and what runs at build. Pull requests #42 and #43.

### Changed

- **`decisions.index.register: none` is allowed in full mode.** It was refused unless `portal.mode` was
  `decisions`, so a full-mode project with no register could not run `check_decision_indexes` at all. Checks 1,
  3 and 4 still do not run, and the run still says so.

### Documentation

- **README, "How it works".** `check_views` checks the deployment in one direction only: rule `floor` fails on
  something the render holds that no capability claims. A new list says what runs at build (no model, no network
  library; mermaid-cli, `helm template` and a Java jar, all local), that only a decision's Status line is read,
  what `quotes` and `floor` need, and that nothing checks the inputs against a running system.

## 0.4.0 (2026-11-21)

Two builds of the same commits write the same bytes, and the page names the commit of the chart, of each bundle
repository and of the kit. Breaking for Action callers that pass `chart`: they must pass `chart-ref` and
`bundle-ref`, and pin the Action to a commit. Pull requests #39 and #40.

### Checks

- **Two builds, same bytes.** The tests build the minimal example twice and a composed example twice, without
  `--date`, and require identical bytes, with nothing normalised.

### Added

- **The page names the commit of each input.** `render_html` takes `--chart-commit SHA` (once) and `--bundle-commit SHA`
  (once per repository holding a `--values` file). It reads the HEAD of each repository with git and refuses a flag that
  is not that commit, and a chart directory or values file that differs from its commit (modified or untracked files;
  ignored ones do not count). The provenance block gains `Chart commit`, one `Bundle commit` for each repository in the
  order first seen, and `Kit`, after the digest. Outside a git repository the part reads `none (not in a git
  repository)` with a note on stderr, and a flag given there is refused. `check_export` checks the three parts and that
  every page carries the same ones; in decisions mode they are optional.

### Changed

- **Breaking:** the Action takes two new inputs, `chart-ref` and `bundle-ref`, and requires both whenever `chart` is
  given: the 40-character commits the chart and the values are checked out at (`bundle-ref` newline-separated, one per
  repository). A malformed value is refused before any tool runs. The Action does not check the chart or the values out
  itself; the build refuses unless they are at those commits and have no uncommitted changes. A caller that passes
  `chart` must add both inputs.
- **Breaking: the Action passes the kit's commit** to `render_html`, since the installed kit can't read it from git. It
  is HEAD of the Action's own checkout (`uses: ./`), or else the name of the directory a commit-pinned Action is
  unpacked into. An Action pinned to a tag or branch gets a warning, and a build with a chart then stops, because its
  page can't name the kit.

### Fixed

- **The Action shows a failing tool's log.** The runner starts bash with `-e`, so a tool that failed ended the step
  before its log was printed, and the later tools never ran. Each step now prints its log and exit code, every step
  runs, and the step fails at the end. The Action's step test runs under the runner's flags.
- **`render_html` takes `--kit-commit` in every mode.** It used to refuse the flag unless `chart: none` was declared,
  so the Action's build with a chart stopped there. A malformed value is still refused. `--source` is still taken
  only with `chart: none`.

## 0.3.4 (2026-11-21)

A browser check for decisions-only portals, front matter and block-quote headings in decision records, a build
dated from its commit, and pinned pyyaml and Chrome. Pull requests #33, #36 and #37.

### Checks

- **A browser check for `portal.mode: decisions`.** `browser_facts` writes the decisions-mode facts (the page ids in
  document order, the page counts by kind, the declared search) and `check_export_browser.mjs` runs ten assertions on
  them: load, page count, navigation, front-page links, back, internal links, search, width at 390 and 1280, print and
  the PDF, and screenshots. The Action runs it in decisions mode too. `export.browser.search` and
  `export.browser.min_pages` are optional in this mode: with no search, the first decision record's id must find its
  page, and with no `min_pages` the PDF must have one page for each page of the portal. The check's lines say which
  values were declared and which are defaults. A decisions-only portal needs no change to its declaration. The
  full-mode check is unchanged.

### Added

- **Front matter in decision records.** A decision record may begin with a YAML front matter block (`---` on line 1,
  closed by `---` or `...`). The heading reader and the rendered page both skip it, so the heading count agrees and
  the block is not shown. Its lines are blanked, so line numbers stay the file's. An unclosed `---` is left alone.

### Changed

- **The build date.** `render_html` without `--date` now dates the build from the committer date of `HEAD`, in UTC,
  in the git repository that holds `paths.root`, not from today. `--date` still overrides it. When the root is not in
  a git repository, or the repository has no commit, the build uses today in UTC and prints
  `render_html: no commit to date the build from; using today (YYYY-MM-DD)` on stderr. A composed build uses the
  composing project's root.

### Fixed

- **Headings inside block quotes were not counted, so such a record failed to render.** A heading written inside a
  block quote (`> ## Note`, also nested) is a heading on the rendered page, but the heading reader skipped it, and the
  render stopped on the mismatch. The reader now strips the quote markers before matching, and a fence opened inside a
  quote ends with it.

### Pinned

- **pyyaml 6.0.3.** `pyproject.toml` requires `pyyaml==6.0.3`.
- **Chrome for Testing 155.0.8059.79.** The Action installs the build puppeteer 25.14.0 names, with
  `@puppeteer/browsers` 3.2.5, into the runner temp directory, and points `PUPPETEER_EXECUTABLE_PATH` and
  mermaid-cli's `--puppeteer-config` at it. A caller that sets `PUPPETEER_EXECUTABLE_PATH` keeps its own browser.
- **The browser check's final line** now ends with the browser's version, for example
  `42 passed, 0 failed (Chrome/155.0.8059.79)`.

## 0.3.3 (2026-11-20)

Connections with Protected by, and the UAF 1.3 Mi row. Pull requests #31, #32 and #34.

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

### Fixed

- **The version string.** `arch_kit.__version__`, which `pip` reports as the package version, said `0.2.0` from
  0.3.0 to 0.3.2. It now says `0.3.3`, and a test fails when it differs from the newest numbered heading here.
- **Tests that failed for reasons outside the code under test (#32):**
  - The composed-build tests each use a private temporary directory, so another suite building at the same time no
    longer fails them.
  - The `test_consumes` assertions print the tool's output when they fail.
  - The `test_no_chart` tests pass a mermaid-cli stub, so they pass in a checkout with no `node_modules`.

## 0.3.2 (2026-11-20)

Census keys as evidence, and outside systems in prose-page citations. Pull requests #28 and #29.

### Added

- **Census keys are a fourth evidence form,** next to a decision id, a repository path and `path:N`. The kit checks
  a key's form; resolving it to a section at the pinned commit is the consuming project's job (#28).
- **Prose pages may cite an outside system by its `XE-` id.** The kit checks the id by form only (#29).

The tag's `arch_kit.__version__` still says `0.2.0`; see 0.3.3.

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
