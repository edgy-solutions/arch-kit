# The project declaration (`arch-kit.yaml`)

The kit holds no project's names, paths or file names. A project declares them once, in a YAML file, and every tool
reads them from there.

## Where the tools look for it

1. `--config FILE` on the command line: `python -m arch_kit --config FILE TOOL ...`;
2. otherwise the environment variable `ARCH_KIT_CONFIG`;
3. otherwise `docs/arch/arch-kit.yaml` under the current directory.

Paths inside the file are relative to the file's own directory, not to the current directory.

## Required keys

```yaml
kit: 1                    # the declaration format version; anything else is refused
paths:
  root: .                 # the architecture content: views/, model/, profiles.yaml, ...
  repo: ../..             # the repository root, where git stamps are read
  decisions: ../../decisions   # the decision records and their registers
```

If the file is missing, `kit` is not 1, or one of the three paths is missing, the tool exits 2. It prints one line
naming the file and the key.

### The portal

```yaml
portal:
  hosting: ci-artifact     # ci-artifact | static-site | none
  audience: public         # public | private
  mode: full               # optional: full (the default) | decisions
```

`portal`, `portal.hosting` and `portal.audience` are all required. The tools that read them, `render_html` and
`check_export`, exit 2 when one is missing, naming the key, so that leaving `portal` out cannot switch the public
checks off. Any other value exits 2 and the message lists the allowed values.

| Key | Value | Meaning |
|---|---|---|
| `portal.hosting` | `ci-artifact` | the export is published as a CI build artifact |
| | `static-site` | the export is published as a static site |
| | `none` | the export is not published |
| `portal.audience` | `public` | anyone may read it: `render_html` needs at least one `--relabel` and one `--barred`, and `check_export` needs at least one `--relabel` (and `--barred`, which it always needs) |
| | `private` | the tools behave as they do without the rule |

`hosting` is declared and validated only. No tool changes what it does because of it. The Action added in step S6
reads it to decide what to publish. `audience` drives the rule above.

`portal.mode` is optional. `full` (the default when the key is absent) is the portal as it has always been.
`decisions` is a portal of the decision records, their index and the roadmap note when the project has one, and
nothing else. The kit does not read or require the capability record or its loader functions (`load_record`,
`model_capabilities`, `resolve_entries`, `quote_of`, `measured_line`, `resolve_quotes`), the views, profiles, slots,
appendix, inventory, the readiness file or the model, and it draws no diagram. The loader needs only the decision
functions (`read_text`, `adr_file`, `adr_lead`, `adr_status`, `index_status`). No chart is needed:
`render_html` takes `--chart`, `--values` and `--release` here but does not require them, and a page rendered without
a chart carries only the date and the declared note, not the chart and digest lines. The roadmap file is optional in this mode:
without it there is no roadmap page and no roadmap entry on the front page. Any other value exits 2 and the message
names `portal.mode`. `examples/decisions-only` is a complete project in this mode.

### A project with no portal: `portal: none`

`portal: none` (the scalar, not the map's `portal.hosting: none`) declares a project with no portal of its own. It
still declares what it consumes, so it needs only `kit`, `portal: none` and `consumes:`; `name` is optional. `paths`
is optional too. When it is present it is read as it always is, and every other declaration still requires it.
`portal: none` with no `consumes:` exits 2. `check_consumes` runs, `render_html` prints
`portal: none: nothing to render`, writes no file and exits 0, and every other tool exits 2 with
`arch-kit: <file>: portal: none: <tool> has no portal to check`.

### What a project consumes: `consumes:`

An optional list at the top level. Each entry names a portal the project depends on, or records in it, and pins it:

```yaml
consumes:
  - portal: example-platform      # required: the consumed project's name (a prefix: lowercase letters, digits, hyphens)
    repo: https://example.org/example-platform.git   # required: a non-empty string with no whitespace
    commit: 0123456789abcdef0123456789abcdef01234567   # required: a full commit, 40 or 64 lowercase hex characters
    records: [ADR-0012, capability:LabelledRecords]    # optional: omitted means the whole portal
    why: "Labels its outbound records with the platform's label model."   # required: one line
    drift: warn                   # optional: warn (the default) or fail
```

A branch, a tag, a short id or uppercase hex in `commit` exits 2. `records` is a non-empty list of strings, each a
decision id or `capability:<name>`; no duplicates. A decision id has the kit-wide record id shape,
`[A-Z][A-Z0-9]*-[0-9]+`, in any prefix and any digit count; it need not match this project's own grammar. Whether it
is a record of the consumed project is checked only by `check_consumes` with a checkout. Two entries with the same `portal`, an unknown key, or a missing required
key exit 2. `drift` is validated and not yet acted on. `render_html` and `check_export` validate `consumes:` and
render nothing from it: their output is the same with or without it.

`check_consumes [--checkout NAME=DIR[:DECL]]...` checks the entries against local clones. `DIR` is a clone of the
consumed project `NAME`, and `DECL` the path of its declaration inside the clone (default
`docs/arch/arch-kit.yaml`). For each entry with a checkout it checks that the pinned commit exists, reads the consumed
declaration at the pin, and checks that each decision id exists at the pin, using the consumed project's own record
grammar (`decisions.records`) and decisions directory. A `capability:` reference prints `checked when composed`: the
tool never imports the consumed project's code. An entry with no checkout prints `not checked: no checkout given`, and
the summary counts it as not checked, which is not a pass. Exit 0 when nothing failed, 1 on a failure, 2 on input.

## Keys a tool needs when it uses them

These keys are optional when the declaration loads. A tool that needs an absent key exits 2 with:

```
arch-kit: <declaration path>: missing key '<dotted.key>' (needed by <tool>)
```

So a project that never runs the data-exchange generator does not need to declare its annotation keys.

| Key | What it names | Needed by |
|---|---|---|
| `loader` | The project's loader module, relative to the declaration file (see [the loader](#the-loader)) | every tool that reads the capability record, a decision record or a register: `capability_phases` and `marks`, and through them `check_views`, `render_html`, `render_profile`, `derived`, `capability_floor`, `check_export` and `check_views_canary` |
| `name` | The framework or system's display name. It is the default attribution line ("built on NAME") and is shortened to "the framework" in decision titles | `data_exchange`, `derived` |
| `model.file` | The SysML v2 model, relative to `paths.root` (or to `--root` where a tool takes one) | `check_views`, `render_profile`, `validate_sysml` |
| `model.package` | The model's top-level package name, which the reference parser must report | `validate_sysml` |
| `exchange.reader` | Opt in to the generated data-exchange section. The only value is `helm-annotations` (see [the exchange reader](#the-exchange-reader)). Absent: no exchange section, no chart render for it, no `--allow-no-kinds`, and `profiles.yaml` `data_exchange.home` must not be given (exit 2 naming the key). Any other value exits 2 and lists the allowed ones | `check_views`, `render_profile`, `render_html` |
| `exchange.annotations.produces` | The workload annotation that lists the topics a workload produces | `data_exchange` |
| `exchange.annotations.groups` | The workload annotation that lists its consumer groups | `data_exchange` |
| `exchange.schema_key` | The JSON Schema extension key that declares a payload's key, label and owning tier | `data_exchange` |
| `registers.follow_ups` | The follow-ups register, a file under `paths.decisions` | `capability_phases` |
| `registers.debt` | The generalisation-debt register, under `paths.decisions` | `capability_phases` |
| `registers.roadmap` | The roadmap file whose table rows name the increments, under `paths.decisions` | `capability_phases` |
| `labels.degraded_mode.heading` | The degraded-mode section's page heading, its table column and the derived table's lead sentence | `render_html`, `derived` |
| `labels.degraded_mode.marker` | The generated-section marker, `<!-- generated: MARKER -->` | `derived`, and through it `check_views` and `render_profile` |
| `labels.degraded_mode.attribute` | The HTML attribute on the capability page's degraded-mode paragraph | `render_html` |
| `labels.degraded_mode.open_row_prefix` | A record row id with this prefix is the open row for "not stated" | `capability_phases`, `derived`, `render_html` |
| `labels.phase.column` | The capability-phases table column that holds the phase, which `render_html` badges, and the heading of the phase on a capability page | `capability_phases`, `render_html`, `browser_facts` |
| `labels.group.column` | The capability-phases table column that holds the group, which `render_html` styles | `capability_phases`, `render_html` |
| `labels.environment.word` | The word for an environment, in the phases document's sentence ("<Word> X is ...") and the evidence cell ("<date>, <word> X, ...") | `capability_phases` |
| `phases`, `floor` | The phases and the floor (see below) | `capability_phases`, `capability_floor`, `render_html`, `browser_facts` |
| `statuses` | The decision statuses (see below) | `capability_phases`, `derived`, `render_html`, `check_views` |
| `views.required`, `views.required_dodaf`, `views.homes`, `views.capability_links` | The views the tree must hold, and where generated sections and capability links live (see below) | `check_views`, `derived`, `render_html`, `render_profile`, `browser_facts` |
| `export.browser.*` | What the browser check opens and how much it expects (see below) | `browser_facts` |
| `readiness.default` | The default readiness document, relative to the chart directory, used when `--readiness` is not given | `render_html`, `render_profile` |
| `decisions.index.*` | The register index and document index file names, the globs that name register homes and indexed documents, the local prefix and the foreign prefixes (see below) | `check_decision_indexes` |
| `derived.dictionary.dir`, `derived.dictionary.terms` | The term dictionary: a directory under the repository root, and the (file, path) pairs the dictionary table shows (see below) | `derived`, and through it `check_views` and `render_html` |
| `files.*` | The content file names under `paths.root`: `profiles`, `slots`, `appendix`, `inventory`, `readme`, `record`, `adr_exemptions`, `annotation_exceptions`. Optional; default is today's name for each (see below) | `check_views`, `check_annotations`, `check_export`, `check_views_canary`, `browser_facts`, `data_exchange`, `derived`, `render_html`, `render_profile` |
| `decisions.index.readme` | Also the name of the decision document index that `capability_phases` reads when no other `decisions.index` key is declared. Optional; default `README.md` | `capability_phases` |
| `decisions.records.prefix`, `decisions.records.digits`, `decisions.records.file_prefix` | The decision record id grammar: `PREFIX-<digits>`, file `PREFIX-<digits>-<slug>.md`, or `<digits>-<slug>.md` when `file_prefix` is false. Optional; default `ADR`, `4` and `true` (see below) | `adr_sections`, `capability_phases`, `check_export`, `check_views`, `derived`, `render_html`, `check_decision_indexes` |
| `decisions.index.register_id.letters`, `.digits` | The register id grammar. Optional; default `2` and `[1, 2]` (see below) | `check_decision_indexes` |
| `derived.roadmap.increments`, `derived.roadmap.fold_ins` | The header cells of the roadmap note's two tables. Optional; default is the original headers (see below) | `derived` |

### The term dictionary

```yaml
derived:
  dictionary:
    dir: ontology            # relative to the repository root, with no `..`
    terms:                   # (file, path) pairs, in the order the table shows them
      - {file: gadgets.yaml, path: gadgets}
```

The generated dictionary section (`views.homes.dictionary`) lists each declared term of the files in `dir`: its kind,
how many entries it has, and the field names, never an entry. `terms` is a non-empty list, each `file` is a bare
`*.yaml` name, and `path` is a dotted path into that file. A `*.yaml` file in `dir` that no term names fails, and so
does a declared file that is absent or a path that does not resolve. The key is required, because the table is built
whether or not the project has a dictionary directory: declare a directory with one small file if it has none.

### Content file names

```yaml
files:                        # under paths.root; every key optional; the default is shown
  profiles: profiles.yaml
  slots: slots.yaml
  appendix: APPENDIX-A.md
  inventory: INVENTORY.md
  readme: README.md
  record: capability-record.yaml
  adr_exemptions: adr-exemptions.yaml
  annotation_exceptions: annotation-exceptions.yaml
```

A value is a plain relative path: no `..`, not absolute, no drive letter. An unknown key under `files` or a bad
value exits 2 and names the key. Messages and help text print the declared name. A declaration without `files`
behaves exactly as before. The decision document index (`README.md` under `paths.decisions`) is
`decisions.index.readme`, and is read from there even when the other `decisions.index` keys are absent.

One more key is not in the list above, because it has no default: `files.alignment`, a directory under `paths.root`.
Every `*.yaml` in it is one alignment record (see [the alignment record](design/alignment.md)), named by its file
stem. A declared directory that does not exist, or holds no `*.yaml`, exits 2 naming `files.alignment`. A project
that declares neither this key nor the loader function below has no alignment records and renders as before.

Another key with no default is `files.composition`: the path of the composition file, relative to the declaration
(not to `paths.root`). Absent means no composition. See [the composition file](#the-composition-file) below.

A loader may instead define `load_alignment(root)`, where `root` is `paths.root`. It returns a dict of record name to
record, in the same shape. The function is optional: it is not one of the names every loader provides. Declaring
`files.alignment` and defining `load_alignment` together exits 2 naming both. The records are validated the same way
whichever route they come by (`arch_kit/schema/alignment.schema.json`), and the first error exits 2. A record name from a loader must match `[a-z0-9][a-z0-9-]*`, the same pattern a file stem must match.

### The flow record: `files.flows` and `load_flows`

A project may declare its flows (see [the flow record](design/flows.md)): each says that one part sends one kind of
record to another, over one channel, and which decision records decided it. `files.flows` names one YAML file under
`paths.root`, with no default; its only key is `flows:`, a non-empty list. Each flow has exactly seven keys:

```yaml
flows:
  - id: FL-001            # FL- then capitals, digits and hyphens
    from: intake          # a part of the project, in its own words, or capability:<name>
    to: depot
    carries: parcel.v1    # the schema key, no whitespace
    via: "broker/parcels" # a topic, a queue or an API path, on one line
    decided_by: [ADR-0001]  # local decision ids, or <prefix>:<id> for a declared foreign prefix; may be empty
    built: false
```

A loader may instead define `load_flows(root)`, returning the same list. It is optional, as `load_alignment` is.
Declaring `files.flows` and defining `load_flows` together exits 2 naming both. A project that declares neither has no
flows and renders and checks as before.

The first error exits 2, as `<file or load_flows>: <path>: <why>`. A schema error names its dotted path
(`flows.0.id`); the later checks name `flows[i].<key>`: a duplicate id, `from` equal to `to`, two flows with the same
`from`, `to`, `carries` and `via`, a repeated id in one `decided_by`, a `decided_by` entry that is not a decision
record, and a `capability:` name that is not in the capability record. A decisions-only portal has no capability
record, so it refuses the `capability:` form. The kit keeps no list of a project's parts, so a part's name is checked
against nothing.

Flows between projects are not decided: a part's name means something only inside its own project, and a flow from
one project's part to another's waits for a ruling on naming parts across a composition.

What the export shows. A project with flows gets one Flows page (`#flows`, linked from the front page's Flows nav): a
count line (`N flows: B built, U not built; G with no decision record.`), a table of the flows in file order, and, when
G is above zero, a list of the flows no decision record covers. Each decision page that some flow's `decided_by` names
gains a "Flows this record decides" list that links to the page. In a full-mode portal each capability page gains the
flows from or to it, and a `capability:` part links to its page. A foreign decision id is plain text. A project with no
flows renders byte for byte as before. `check_export` adds one check when the project declares flows: exactly one
`data-flows` page, its `data-flow` row ids equal the declared ids in order, and its count line agrees with the records.
The ok line then ends its shape with `N flows; `. The golden example is `examples/flows`.

In a composed build each member that declares flows gets its own `NAME--flows` page and a Flows list in its front
block, so two members may both have an `FL-001`. A group without flows gets neither. `check_export` then checks, for
the portal and each member, that a group with flows has exactly one `NAME--flows` page and one front-page link to
it, and that a group without flows has neither; a member's `files.flows` is read from its declaration at the pin.

### The component record: `files.components`, `components:` and `load_components`

A project may declare its components: each is one part of a system, with what it is for, how it is wired, how it signs
in, where its data goes, the plane it sits on, what it serves, how far along it is, and the evidence. `files.components`
names one YAML file under `paths.root`, with no default; its only key is `components:`, a non-empty list. Each
component has exactly ten keys, all required:

```yaml
components:
  - id: CO-001                  # CO- then capitals, digits and hyphens; unique
    name: depot-sync            # a part name: a letter or digit, then letters, digits, dots, underscores or hyphens; unique
    purpose: pushes parcels to the depot     # purpose, wiring, sign_in and data_path: one non-empty line each
    plane: hub                  # a part name, and one of components.planes
    wiring: reads the parcel topic, writes the depot API
    sign_in: depot service token
    data_path: locker to depot
    serves: [pickup]            # one-line strings; may be empty; no repeats
    status: built               # measured, built, accepted or proposed
    evidence: [src/depot_sync.py:2]   # at least one; no repeats
```

The top-level `components:` map of the declaration holds the two lists the checks read:

```yaml
components:
  planes: [edge, hub]           # required: a non-empty list of unique part names
  results: [results]            # optional: repository paths (files or directories) that hold measured results
```

Any other key under `components:` exits 2. The map is read only when components are loaded, that is when
`files.components` or `load_components` is declared; it is then required. A project that declares neither has no
components, needs no `components:` map, and renders and checks as before. A `results` path follows the rules of
`files` values: relative, no `..`, no drive letter.

A loader may instead define `load_components(root)`, where `root` is `paths.root`, returning the same list. It is
optional, as `load_flows` and `load_alignment` are, and is not one of the names every loader provides. Declaring
`files.components` and defining `load_components` together exits 2 naming both.

The first error exits 2, as `<file or load_components>: <path>: <why>`. A schema error names its dotted path
(`components.0.id`); the later checks name `components[i].<key>`, in this order: a repeated id, a repeated name, a
plane that is not in `components.planes`, a repeated `serves` or `evidence` item, an evidence item that does not
resolve, and a status whose evidence is not enough. An evidence item resolves when it is a decision record (a local id,
or `<prefix>:<id>` for a declared foreign prefix), or a path that exists under the repository (relative, no `..`, no
drive letter), or `path:N`, a file under the repository with at least N lines (N from 1; a directory does not take a
line). `built` needs at least one `path:N` item; `accepted` needs at least one decision record; `proposed` needs
nothing more.

`measured` is the one check that does not refuse. A `measured` component with no evidence item whose path (without any
`:N`) is, or sits under, a `components.results` path is reported on stderr as
`<tool>: <file or load_components>: components[i].evidence: measured, but no evidence is under components.results`,
one line per component in file order, and the load goes on.

### The census: `census:` and census keys

A member may keep a census: a guide file, or a directory of files, whose numbered sections hold its decisions. `census:` is an
optional top-level key naming that file or directory, a repository path (relative to the repository root, the way evidence paths are, not under `paths.root`):

```yaml
census: AGENTS.md
```

It must be a string, not absolute, with no drive letter and no `..`; a backslash reads as `/`. A value that is not a
string exits 2 with `census: must be a repository path`; an unsafe one exits 2 with
`census: must be a relative path inside the repository`. Whether the file or directory exists is checked where a census key is
used, not when the key is read.

A **census key** is a fourth evidence form, beside a decision record, a path and `path:N`. It is accepted as an item of
`rows.{j}.evidence` in an alignment record, as an item of `components[i].evidence`, and as a roadmap `home`. Its
grammar, written `[member] [path] §section[ (variant)][.bullet]`:

- `member`: a mesh member name (lower case letters and digits, hyphen-separated), optional, followed by a colon or a space
  (`member:§KEY` or `member §KEY`).
- `path`: a path, optional, and it contains a `.` or a `/`. It is accepted as written, and contains no `:`.
- `section`: starts with a digit; its letters are lower case, with hyphens between parts (`4`, `4p`, `4g2`, `4p-2`).
- `variant`: an optional ` (<name>)` after the section, telling apart two sections that share a number
  (`§4a (OTel).1`, `§4a (inventory)`); the name starts with a letter, then letters, digits and hyphens, after one space.
- `bullet`: a decimal number from 1, after a dot, optional (`§7.1`).

So `§4p.3`, `AGENTS.md §4p.3`, `other-member §4p.3`, `other-member:§4p.3` and `other-member AGENTS.md §4p.3` are all census keys. A value without the
`§` section (`4p.3`, `§4.`, `§4.0`, `contract§4`, `§Part`, `§4P`) is not one, and the other forms apply to it as before.

The kit checks the form only. With a `member`, it accepts the key: the other members are not known to it. Without one, the
key must be able to name this project's census: `census:` is declared (otherwise `<key> is a census key, and the
project declares no census (census:)`), the file or directory exists (`<key> cites the census <census>, which does not exist`). A `path` in a key is accepted as
written; the mesh loader resolves the key against the declared census. The refusal is at the
same location as any other unresolved evidence. Resolving the section at the pinned revision is the mesh loader's
job; it reports a key that does not resolve as a finding.

A census key counts as a decision record for a `components` status of `accepted` and for a roadmap `home`. It does not
count as the file and line `built` asks for: a `built` component with a census key but no `path:N` is
reported on stderr, not refused, as `<tool>: <file or load_components>: components[i].evidence: built, but the only
evidence is a census key (no path:N)`. `built` asks for evidence that the thing exists at a pinned commit, which a
census key alone is not; the kit reports these claims rather than refusing them, so they can be counted. One with neither still
exits 2 (`built needs a file and line (path:N) in evidence`). `components.census_only_built(components, ctx)` returns
the ids of the reported components, in record order. `owed` in an alignment row stays decision-only.

### The roadmap record: `files.roadmap` and `load_roadmap`

A project may declare its roadmap as a record: an ordered list of increments, each with what it isolates, where its
decision lives, which earlier increments it depends on, and how far along it is. `files.roadmap` names one YAML file
under `paths.root`, with no default; its only key is `roadmap:`, a non-empty list. Each increment has these keys, and
no others (there is no date key):

```yaml
roadmap:
  - id: RM-001                  # RM- then capitals, digits and hyphens; unique
    increment: Offline pickup   # one non-empty line; unique, because capability records name increments
    isolates: whether a locker accepts a parcel with no depot link   # one non-empty line
    home: ADR-0001              # a decision record, local or <prefix>:<id> for a declared foreign prefix
    depends_on: []              # ids of EARLIER increments; may be empty; no repeats
    status: measured            # measured, built, accepted or proposed
```

`home` is optional only when the status is `proposed`; when present it must resolve to a decision record. An unquoted
YAML date (`2026-11-19`) in any field exits 2, and `increment` and `isolates` must not hold a date such as `2026-11`
or `2026-11-19`. `depends_on` names only increments that come earlier in the list, so there are no cycles.

A loader may instead define `load_roadmap(root)`, where `root` is `paths.root`, returning the same list. It is
optional, as `load_components` is, and is not one of the names every loader provides. Declaring `files.roadmap` and
defining `load_roadmap` together exits 2 naming both.

The record and the roadmap note are one roadmap, not two. When either route is declared and `registers.roadmap` names a
file that exists under the decisions directory, the load exits 2 with
`files.roadmap: is declared, and the roadmap note decisions/<name> exists; use one`. A `registers.roadmap` that names
no file is not an error, and a project that declares neither route is unchanged.

The first error exits 2, as `<file or load_roadmap>: <path>: <why>`. A schema error names its dotted path
(`roadmap.0.id`); the later checks name `roadmap[i].<key>`, each over every increment before the next starts, in this
order: a repeated id, a repeated increment, a date in `increment` or `isolates`, a repeated `depends_on` item, a
`depends_on` item that is the increment itself, comes later or is no increment id, and a `home` that is missing (and
the status is not `proposed`) or does not resolve.

### The prose pages: `files.pages` and `load_pages`

A project may write its overview and walkthroughs as prose pages. Every record a page cites is checked to exist, and a
status it claims is checked against the record, so prose cannot claim more than the records do. `files.pages` names a
directory under `paths.root`, with no default. Every `*.md` file directly in it (not in a subdirectory) is one page,
read in sorted order, and its id is the file stem (lowercase letters, digits and hyphens). A directory that does not
exist exits 2 as `<dir>: (record): is not a directory`. A file opens with front matter between a first line `---` and
the next line that is exactly `---`; the body is everything after it:

```markdown
---
title: A parcel arrives offline   # one non-empty line
kind: walkthrough                 # overview or walkthrough; at most one page may be the overview
order: 2                          # optional integer >= 1; walkthroughs sort by (order, id), none last
---
A courier puts a parcel in a locker. The first step is [[RM-001|built]], on the flow [[FL-001|built]].
```

The front matter holds only `title`, `kind` and `order`; any other key (`id` and `body` included) exits 2 as
`<file>: <key>: unknown key`. A file with no front matter exits 2 as `<file>: (record): must open with front matter
between --- lines`.

A loader may instead define `load_pages(root)`, where `root` is `paths.root`, returning a list of
`{id, title, kind, body}` with an optional `order`. It is optional, as `load_roadmap` is, and is not one of the names
every loader provides. Declaring `files.pages` and defining `load_pages` together exits 2 naming both.

A citation is `[[ident]]` or `[[ident|status]]`, in the body only. It is not one inside a fenced code block (a line of
at most three spaces then ``` or ~~~, closed by the same marker) or an inline code span; an indented code block is not
special-cased. The ident is resolved in this order: `CO-...` against the components, `RM-...` against the roadmap,
`FL-...` against the flows, `alignment:<name>` against the alignment records, `XE-...` as an outside system (defined
once in the member's README and checked by form only, so no record is loaded), and anything else as a decision id, local
or `<prefix>:<id>` for a declared foreign prefix. A status is one of `measured`, `built`, `accepted`, `proposed`, and
applies to components and increments (it must equal the record's status) and to flows (only `|built`, which holds when
the flow's `built` is true). A decision, an alignment record or an outside system carries no status. The renderer's
`href(kind, ident)` receives the kind `decision`, `component`, `increment`, `flow`, `alignment` or `element`.

The checks run in this order, and the first failure exits 2: the schema (`<file>: <key>: <why>` on the directory route,
`load_pages: pages[i].<key>: <why>` on the loader route), a repeated id (loader route), a second overview
(`only one page may be the overview; <id> already is`), then each citation, as `<where>: line N: <why>`. N is the
1-based line in the file, front matter counted, on the directory route (where `<where>` is the file), and the line in
`body` on the loader route (where `<where>` is `load_pages: pages[i].body`). The reasons are `[[X]] does not resolve`
(with `: the project declares no components`, `increments`, `flows` or `alignment records` when the project declares
none), `[[X|s]]: s is not a status (measured, built, accepted, proposed)`, `[[X|s]]: a flow is built or not; only
|built applies`, `[[X|built]] says built; X is not built`, `[[X|s]]: only components, increments and flows carry a
status` and `[[X|s]] says s; X is <the record's status>`. Each record set is loaded at most once, and only when a
citation needs it.

### The decision index

```yaml
decisions:
  index:
    register: REGISTER.md          # the register index: one row per register id
    readme: README.md              # the document index: every indexed document is named in it
    register_homes: [ADR-*.md, DEBT.md]     # where register ids are declared, and their status tokens
    indexed: [ADR-*.md, PLAN-*.md, DEBT.md, REGISTER.md]   # each must be named in the readme
    local_prefix: loam             # a `loam:ADR-NNNN` citation must resolve to a document here
    foreign:                       # other repositories this corpus cites, in order
      - prefix: ferro
        pin_check: scripts/pin-stub.sh   # repository-relative; optional
```

With `files.composition` declared, the foreign prefixes come from the composition file (below) and `foreign` must be
absent: declaring both exits 2.

`check_decision_indexes` reads it. The files are under `paths.decisions`. Every key is required except `foreign`
(default: none) and `pin_check` (default: no pin check for that prefix); `register_homes` is also not read when the
register is `none` (below). `register_homes` and `indexed` are lists of
file globs with no spaces in them. A prefix is lowercase letters, digits and hyphens, starting with a letter. A bad or
missing key exits 2, and the message names it.

- **`register: none`** declares that a decisions-only project has no register. It is allowed only with
  `portal.mode: decisions` (full mode exits 2), `register_homes` and `register_id` must then be absent, and `readme`,
  `indexed` and `local_prefix` are still required. Checks 1, 3 and 4 do not run, and the run says so. A missing
  `register` key is not this: it still exits 2.

  ```yaml
  portal: {mode: decisions, hosting: none, audience: private}
  decisions:
    index: {register: none, readme: README.md, indexed: ["[0-9]*.md"], local_prefix: larkspur}
  ```

- **`pin_check`** is a script that checks the citations of one foreign repository are pinned to the commit the
  project read. The tool runs it from the decisions directory with one argument, the repository root (both given as
  relative paths), and treats a non-zero exit as drift. Its stdout is the list of pins. Set `PINS_OUT` to a file to
  receive the lists of all the pin checks, one after another.
- **Messages** are built from the declaration. "Known repos: A, B." lists `local_prefix`, then each foreign prefix in
  order. With more than one foreign entry the per-foreign summary lines repeat once per entry, in order.

Phase 2's composition record (`docs/design/composition.md`, ruled 2026-11-18) puts one table of known project names,
for citations, compositions and consumption, in the composition file. The prefixes move there at its step P2-2.
Until then `local_prefix` and `foreign` are the shape.

## The composition file

`files.composition` names a file beside the declaration that lists the projects a composing portal knows. It is
the one table of known projects (see [composition](design/composition.md)): the decision index check reads its
repository prefixes from it.

```yaml
composition: 1
members:
  - name: example-platform                 # a project name
    repo: https://example.org/example-platform.git
    commit: 0123456789abcdef0123456789abcdef01234567   # a full commit
    declaration: docs/arch/arch-kit.yaml   # optional: its declaration in its repository; this is the default
    lists: {relabel: platform-relabel, barred: platform-barred}   # required: slot names, never paths or values
consumers:                                  # optional
  - name: example-app
    repo: https://example.org/example-app.git
    commit: 89abcdef0123456789abcdef0123456789abcdef
    declaration: docs/arch/arch-kit.yaml   # optional, as above
```

Every error exits 2 and names `files.composition` and the key within the file. `composition` must be 1 and
`members` non-empty. Names are project names (lowercase letters, digits and hyphens, starting with a letter),
unique across `members` and `consumers` together, and none may equal this project's own
`decisions.index.local_prefix`. `repo` and `commit` follow the rules of `consumes:`. `declaration` is a plain relative
path with no `..`. `lists` has exactly `relabel` and `barred`; each value is a slot name matching
`[a-z0-9][a-z0-9-]*`, used once in the whole file, and never a path (a `/` or a backslash is refused). A project with
`portal: none` that declares `files.composition` exits 2: it composes nothing.

With a composition, `check_decision_indexes` takes the foreign prefixes from the file, members first and then
consumers, each pinned at its `commit`, and runs no pin check for them. Its summary names each prefix and the first
seven characters of its commit, and says that each cited record existing at the pin is checked when composed, not
there. `PINS_OUT`, when set, receives a line `- <prefix> <commit> -` for each, in the shape of the pin list a pin check
prints (citing file, prefix, commit, cited path), with `-` where the composition file has no value. Without a
composition the tool's input and output are unchanged.

### The composed build

With `files.composition`, `render_html` and `check_export` build one document of every group's records: the composing
portal's own, then each member's in file order. Both take `--checkout NAME=DIR` for every member and every
consumer in the file (a missing, unlisted or repeated NAME, a DIR that is not a git repository, or a commit not in
its DIR exits 2, naming `members[i]` or `consumers[i]`, never the project).

- The composing portal must have `portal.mode: decisions`: a composed portal is decisions-only for now.
- Each member is read at its pin in a temporary local clone (`git clone --shared --no-checkout`, then a detached
  checkout), removed when the build ends. The source clone is never changed. A member with `portal: none`, a
  `portal.mode` other than `decisions`, or its own `files.composition` is refused. Each group renders in its own
  process by its own declaration and loader at the pin (the member's loader runs, a consumer's never does).
- Page and anchor ids become `NAME--X`, so two groups may both have `ADR-0001`. The front page has one block per
  group, in that group's words.
- A "Consumed by" block lists the consumers of a record or a portal, read as data from each consumer's declaration at
  its pin; a "Consumes" block lists what a member consumes. A consumer with `portal: none` or a non-public audience
  shows only its name, repository and commit, never its `why`. No link leaves the page.
- `check_export` on a composed export runs the barred, provenance, network, size, links and relabel checks and a
  `members` check; the `decisions` check is not run.
- `--list SLOT=FILE` (repeatable, on both tools) gives the list for a slot of `lists:` in the composition file: a
  `relabel` slot holds a relabel list, a `barred` slot a barred list. An unknown or repeated slot, or an unreadable
  file, exits 2. A public composing portal needs every slot, plus its own `--relabel` and `--barred`; a private one
  may omit slots, and one stderr line names the slots that ran empty.
- A member's relabel slot is applied to that member's records as it renders. The final pass over the document
  applies the portal's own `--relabel` lists in order, then each member's relabel slot in file order. Two rules with
  the same pattern and different replacements in different lists exit 2, naming both lists and rule numbers.
- The leak scan and `check_export` run every relabel and barred list together. A finding names its list (a slot name,
  or `--relabel N` / `--barred N`), the rule number and a count, never the value.
- A public composing portal refuses a member whose own audience is not public, before any clone is made; the
  message names the position (`members[i]`), not the project.
- Each "Consumed by" and "Consumes" entry on a group of this export shows a pin state,
  `<span class="pin" data-pin="STATE">`, from the consumer's commit C against the consumed group's commit D (the
  composition file's pin for a member, `HEAD` for the composing portal). Per named record, first match wins:
  `pin-not-found` (C is not in the repository), `record-not-found` (no file of that id at C, by the consumed project's
  grammar; a fifth state the design did not name, so a record that was never there is not shown as current),
  `superseded` (the record's status at D is declared with `in_force: false`), `changed` (the record's file at D is
  absent or differs from C's), `current`. An entry with no `records` shows one state: `pin-not-found`, else `changed`
  if any file of the decisions directory differs between C and D, else `current`. The composed build never fails on a
  state. With no `statuses` declared, `in_force` is unknown and `superseded` never shows.
- `check_consumes` compares each entry with a `--checkout` against that clone's `HEAD`: a named record (or the decisions
  directory, for an entry with no `records`) changed since the pin prints `warn: consumes[i]: changed since the pin:
  IDS` with `drift: warn` (the default, exit unchanged) and `FAIL: ...` with `drift: fail` (exit 1). It cannot compute
  "superseded since": that needs the consumed project's loader, and the check imports no other project's code. Its
  summary line says so.
- A member may declare `portal.composed_in: NAME`, which adds one sentence to its own standalone render naming the
  composing portal. Without the key its output is unchanged.

## A complete example

The kit's own tests use this declaration. Every value is made up.

```yaml
kit: 1
paths:
  root: .
  repo: .
  decisions: .
loader: loader.py
name: Example
model:
  file: model/example.sysml
  package: Example
exchange:
  annotations:
    produces: example.org/produces-topics
    groups: example.org/consumer-groups
  schema_key: x-example
registers:
  follow_ups: FOLLOW-UPS.md
  debt: DEBT.md
  roadmap: ROADMAP.md
readiness:
  default: ../scripts/READINESS.md
labels:
  degraded_mode:
    heading: Isolated behaviour
    marker: isolated-behaviour
    attribute: data-isolated
    open_row_prefix: IS-
  group:
    column: Team
  environment:
    word: site
```

The labels are the words the kit prints for three concepts. The kit holds none of them. Two identifiers follow from
them: the CSS class that marks the first row of a new group is the group column, lowercased, with spaces as hyphens,
then `-start` (`team-start` here), and the environment word starts a sentence with its first letter in upper case
("Site X is ...").

## The loader

The kit holds the rules and the rendering, but not the project's file formats. Reading the project's files is the
loader's job. The loader is a Python module that the project writes, and `loader:` declares it. The kit imports it
once, by path.

The loader provides the names in `arch_kit/tools/seam.py`, where they are written as a `typing.Protocol` with one line
each:
- `load_record`: the capability record;
- `model_capabilities`: the capabilities in the model;
- the decision records: `read_text`, `adr_file`, `adr_lead`, `adr_status` and `index_status`;
- the registers and the roadmap: `register_rows`, `register_subjects` and `roadmap_rows`;
- the readiness document: `resolve_entries`, `quote_of`, `measured_line` and `resolve_quotes`;
- `KEY_NAMES`, a map from each neutral key to the project's own name for it.

The kit's tests check that every name exists on the kit's own fixture loader, `arch_kit/tools/testdata/loader.py`.
That file is a minimal working loader for a made-up format, and a starting point for writing one.

### The neutral record

`load_record` returns the record with these keys, whatever the project calls them on disk:

| Neutral key | What it holds |
|---|---|
| `groups` | for each parent capability in the model, the group it belongs to, shown beside its capabilities |
| `environments` | the environments a measurement can run in. Every entry must name one of them |
| `entries.<key>.environment` | the environment that entry's measurement ran in |
| `capabilities.<name>.degraded_mode` | what the capability does when it is cut off |

All other keys keep the names that `arch_kit/schema/record.schema.json` gives them. The loader maps the keys after it
parses the file. It should refuse a file that already uses a neutral key, so that two names never mean the same thing.

The kit validates the returned record against `arch_kit/schema/record.schema.json` (JSON Schema draft 2020-12), with
`jsonschema==4.26.0`. Messages print the project's own key names through `KEY_NAMES`, including schema errors, so
the output reads in the project's own words.

### When it fails

All of these exit 2:

| Failure | Message |
|---|---|
| No `loader` key | `arch-kit: <declaration>: missing key 'loader' (needed by <tool>)` |
| The file does not exist | `arch-kit: <declaration>: loader file <path> not found` |
| The record breaks the schema | `<record>: <where>: <what>`, for the first place it breaks |

## Phases, statuses, views and the browser check

### `phases` and `floor`

```yaml
phases:                         # strongest first; a capability takes the first phase whose rule it meets
  - name: measured
    when: [measured]
    badge: m
  - name: proposed
    when: [{status: Proposed}, still-open, pending]
    badge: a
floor: built unmeasured         # a phase name: everything deployed must be claimed at or above it
```

`when` lists rules, and a capability meets a phase if it meets any one of them. The rule vocabulary is fixed by the
kit:

| Rule | A capability meets it when |
|---|---|
| `measured` | the record gives it a `measured` entry |
| `built` | the record gives it a `built` entry |
| `{status: WORD}` | it cites a decision record whose status line starts with the lead of the declared status WORD |
| `still-open` | a decision record names it still open |
| `pending` | the record lists a pending decision for it |
| `rows` | the record lists a register row for it |

`badge` is one of the five palette keys `m`, `b`, `a`, `p`, `r`, which pick the colours of the phase badge. A phase's
CSS class is its name with spaces turned into hyphens. A capability that meets no rule has no phase, and that fails
the render. `floor` is a phase name; the floor phase and every phase declared above it satisfy `capability_floor`.
An unknown rule, an unknown status word, a duplicate phase name, a `floor` that is not a phase and a `badge` that is not
a palette key each exit 2.

### `statuses`

```yaml
statuses:
  - word: Accepted       # as the decision index and a Sources table's Decision column write it
    lead: accepted       # how a record's status line starts, lowercase
    in_force: true
  - word: Proposed
    lead: proposed
    in_force: true
    sources_check: true  # a Sources row marked with this word and its record's lead must agree
  - word: Superseded
    lead: superseded
    in_force: false
```

`in_force` has two meanings. `derived` requires a record with an in-force status to be cited by a view, unless it is
exempt. And an in-force status is the only kind a capability may cite: `capability_phases` refuses a capability that
cites a record whose status is declared with `in_force: false`, or is not declared. `in_force` defaults to false. A
status line that starts with no declared lead is a failure in `derived`.

### `views`

```yaml
views:
  required: [Op-Cn, Rs-Sr]                  # views the tree must hold
  required_dodaf: [OV-1, OV-2]              # DoDAF outputs some view must export
  homes:                                    # generated-section name -> the view that holds it
    capability-phases: St-Rm-P              # also: dependencies, taxonomy, dictionary, trace, and the marker declared in labels.degraded_mode.marker
  capability_links: [St-Tx, St-Rm-P]        # views whose capability names link to the capability pages
```

The UAF grid meanings stay fixed in the kit (`uaf.py`): the capability taxonomy, the traceability matrix and the
operational and resource process views are the grid cells `check_views` reads for its `capabilities` and `trace` rules.
The ids that hold them are the project's own.

### `export.browser`

```yaml
export:
  browser:
    views:
      table: Rs-Cn          # the view with the widest table; phone, zebra and screenshot checks open it
      diagram: Op-Tx        # diagram screenshot, print and table-width checks
      profile_only: Sc-Sr   # a view with no export in one of the profiles
    search:
      phrase: Which resource talks to which
      finds: Rs-Cn          # the view whose page holds the phrase
    min_pages: 30           # the least pages the print PDF may have
    min_tables: 30          # the least tables with a min-width header
    min_tokens: 1000        # the least words the mid-word wrap check must measure
    expect_wide_table: true # optional: the table view holds a table wider than its container at 1280
```

`browser_facts` reads these with the model, the record, the decision records and the views, and writes the counts
the browser script expects: the number of views, pages by kind, the phase badges, the widest table, the number of
group starts and the ids above. The script exits 2 without `--facts`. `wide_table_columns` is the widest table in the
`table` view's source; when the data-exchange home is that view, the generated Exchanges table counts too.

### Decision record and register ids

```yaml
decisions:
  records:              # optional; a record id is PREFIX-<digits>, its file PREFIX-<digits>-<slug>.md
    prefix: ADR         # capital letters and digits, starting with a letter (default ADR)
    digits: 4           # an integer 1..8 (default 4)
    file_prefix: true   # true or false (default true): false names a record file <digits>-<slug>.md
  index:
    register_id:        # optional; the register id grammar
      letters: 2        # an integer 1..6: that many capital letters (default 2)
      digits: [1, 2]    # [min, max], 1 <= min <= max <= 6 (default [1, 2])
```

`decisions.records` may be declared without `decisions.index`. Messages that print the record form (`ADR-NNNN`)
print the declared prefix and one `N` per digit. A bad value exits 2 and names the key. The `register_homes` and
`indexed` globs are the project's own and are not changed by `records.prefix`.

With `file_prefix: false` a record file is `0007-use-a-queue.md`, and its id is still `ADR-0007`: ids are what prose
cites and what page ids are made from, and only the mapping between a file name and an id changes. The prefix itself
cannot be empty, because an id of bare digits would match years in prose. A value that is not true or false exits 2.

### The roadmap note's tables

```yaml
derived:
  roadmap:              # optional; the defaults are shown
    increments: ["#", increment, what isolates, home, depends on]
    fold_ins: [row, slice, folds into, why it costs the increment nothing]
```

Each is a non-empty list of distinct, non-empty header cells. The columns are still read by position, so a declared
header needs at least as many cells as the default (5 and 4), else exit 2 naming the key. `derived.dictionary` keeps
its own unknown-key check; `derived` may hold `dictionary` and `roadmap`.

## Formerly fixed, now declared

Each of these was fixed in 0.1.0. The default is the old fixed value, so a declaration that does not use the key
behaves as before.

- The content file names under `paths.root`: `files.profiles`, `files.slots`, `files.appendix`, `files.inventory`,
  `files.readme`, `files.record`, `files.adr_exemptions`, `files.annotation_exceptions`.
- The decision document index name under `paths.decisions`: `decisions.index.readme` (default `README.md`).
- The decision record id and file name: `decisions.records.prefix`, `decisions.records.digits` and
  `decisions.records.file_prefix` (default `ADR`, `4` and `true`, so `ADR-NNNN-<slug>.md` and the citation
  `prefix:ADR-NNNN`; `false` drops the prefix from the file name only).
- The register id grammar of `check_decision_indexes`: `decisions.index.register_id.letters` and `.digits` (default
  two capital letters and one or two digits, such as `XY-7` and `QZ-01`).
- The roadmap note's table headers: `derived.roadmap.increments` and `derived.roadmap.fold_ins`.
- `ontology/*.yaml` is `derived.dictionary.dir`, already declared; no kit code names that path otherwise.

Still the loader's, not the declaration's: the status line of a decision record and of the roadmap note (a
`## Status` section, else a `Status:` line) is read by the project's loader (`adr_status`, `adr_lead`,
`roadmap_rows`), so the kit fixes nothing about it.

## The exchange reader

`exchange: {reader: helm-annotations}` turns on the generated data-exchange section, read from a `helm template` render of the chart. The reader is written for one platform's chart and expects these names, which are not declared and not renamed:

- ConfigMaps `egress-kinds`, `egress-routes`, `egress-assembler-config`, `egress-intake-config` and `destinations-deployment`;
- workloads `egress-gate*`, `egress-forwarder`, `egress-assembler` and `egress-intake`;
- one StatefulSet `redpanda-<tier>` per tier, and a special tier and broker named `hq`;
- topic annotations of the form `broker/topic`, under the keys `exchange.annotations.produces` and `.groups`.

A project whose chart is not shaped that way declares no exchange. With no `exchange` key, `check_views` skips the exchange rules and the capability floor (the floor reads the reader's model), and `render_html` writes no exchange table or diagram. The chart is still read by the quotes rule, the built-template phase rule and the readiness document. A consumer-side reader is Phase 2.
