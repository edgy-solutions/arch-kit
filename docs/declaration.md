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
