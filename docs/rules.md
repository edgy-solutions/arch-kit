# The checks

The kit holds three checks:

- `check_views` checks the source: the views, the model and the record.
- `check_export` checks the rendered HTML file.
- `check_export_browser.mjs` checks the rendered file in a real browser.

All three exit 0 when every check passes, 1 when a check fails, and 2 when an input is missing or bad. A check that
cannot run is never reported as passing.

## `check_views`: 17 rules on the source

`check_views` writes one `FAIL: <rule>: <what>` line per finding on stderr. When nothing fails, it prints
`ok: 17 rules, N views`.

| Rule | Fails when |
|---|---|
| `exports` | a view exports an id that `APPENDIX-A.md` does not name for it |
| `appendix-a` | `APPENDIX-A.md` has the wrong header, a malformed or duplicate row, a view with no row, or keys out of step with `profiles.yaml` |
| `view-files` | a view file is missing, its first line is not `# Name (ID)`, or a `views/*.md` file is not listed |
| `slots` | a slot is used but not registered, registered but not used, has no fill or source, or disagrees with the slot table in `INVENTORY.md` |
| `links` | a relative link in `README.md`, `INVENTORY.md`, `APPENDIX-A.md` or a view does not resolve |
| `decision-links` | a decision-record link's text is not `ADR-NNNN §LABEL`, points at another record, names a section that does not exist, or has the wrong fragment |
| `sources-table` | a Sources table has the wrong header or cell count, a row with no link, or a Decision or Evidence value outside the vocabulary in `README.md` |
| `marks` | a cited record is missing or has no status line, a row marked Proposed disagrees with the record, or an Evidence cell disagrees with the record's status line |
| `model` | a `<!-- model: Pkg -->` marker names a package the model lacks, or a top-level package is named by no view |
| `capabilities` | the traceability view names an undefined capability, or a model capability is missing from the taxonomy view's Sources |
| `trace` | an activity or function in the traceability view is missing from the process views, or a leaf activity is missing from the traceability view |
| `outputs` | a required view or output is absent, or a data-exchange id does not resolve |
| `generated` | the data-exchange marker is not present exactly once, in its home view |
| `phases` | the capability-phases marker is missing, misplaced or repeated, or the capability record fails its check (every citation resolves; see the [methodology](METHODOLOGY.md)) |
| `derived` | a derived-table marker is not present exactly once in its home view, or the table cannot be built |
| `quotes` | text on the barred list appears in an evidence cell or in the record |
| `floor` | something the deployment renders (a workload, a kind, a flag or a route) is claimed by no capability, or is claimed only by a capability in a phase below the declared `floor` (see [the declaration](declaration.md#phases-statuses-views-and-the-browser-check)) |

### A record the schema refuses

The capability record is validated when it loads, before any rule runs. A record that breaks the schema (for
example, a capability with no degraded-mode entry) makes the tool exit 2, naming the first place it breaks. Before the
loader seam, `phases` reported the same record as a finding, with exit 1. The same records fail as before. They now
fail as bad input, and on their own, not alongside other findings. The message still uses the project's own key name.

### Partial runs

`quotes` and `floor` need the chart, its values, the release name, the readiness document and the barred list. A call
that leaves out any of these exits 2. `--allow-partial REASON` runs the other fifteen rules, and the ok line names the
two it did not run and the reason given.

### Proving the checks can fail

`check_views_canary` copies the tree, breaks it once for each case, and requires `quotes` and `floor` to fail with the
right code. A check that has never failed on a broken input is not yet known to work.

`validate_sysml` works the same way. It passes only when the model parses clean **and** the reference parser refuses
two copies that were broken on purpose.

## `check_decision_indexes`: the decision indexes

An index drifts where nobody is looking. This tool asks the directory, not the author's memory, and runs four checks
over `paths.decisions`, with every name taken from [`decisions.index`](declaration.md#the-decision-index):

1. **Ids and rows.** Every register id declared in a register home has a row in the register index, and every row is
   a real id. The ids come from declaration sites (a bolded heading or a table row), not from a scan of prose, so a
   platform designation such as `UH-60` is not mistaken for one. The register index is left out of the evidence it is
   checked against, or every row would vouch for itself.
2. **Documents.** Every document that matches an `indexed` glob is named in the document index.
3. **Status.** Every row's status equals its home's declared status token, as an exact string.
4. **Tokens.** Every row's home has a token, so that check 3 cannot be skipped by absence.

Citations are checked too. A `prefix:ADR-NNNN` citation with a prefix the declaration does not know is a finding. One
with the local prefix must resolve to a document here. One with a foreign prefix is checked for form, and, where a
`pin_check` is declared, for its pin. An unqualified `ADR-NNNN` means this repository.

**What these do not prove.** Check 3 shows that the index agrees with the home. Both can be wrong together. Only a
person reading the home establishes that a status is true, and a clean run says so. Nor can the tool see another
repository: that a cited file exists at a pinned commit is for a check that can reach it, which needs the network.
Status is compared, never inferred; an earlier attempt to pattern-match prose gave false positives and false negatives
both. Exit 0 clean, 1 drift, 2 input.

**No register.** With `decisions.index.register: none` (allowed only when `portal.mode` is `decisions`) the project
declares that it has no register. Checks 1, 3 and 4 do not run, and every run prints
`checks 1, 3 and 4: not run: decisions.index.register is none`, whether it is clean or not. Check 2 and the citation
checks run as before. Leaving the register out of the declaration is not the same thing: that exits 2, because absence
must not answer as agreement.

## `check_export`: the HTML file

```
python -m arch_kit check_export --export FILE --barred FILE [--barred FILE ...] [--root DIR] [--relabel FILE ...]
```

It checks:
- that the views in the file equal the views `check_views` counts;
- the barred list and the relabel list (see below);
- each page's provenance line;
- the content security policy, with no remote references or scripts in diagrams;
- the size of the file;
- the internal links, the diagrams and the declarations.

With `portal.mode: decisions` it runs only these checks: the barred list and the relabel list, each page's
provenance line, the content security policy and the size of the file, the internal links, and the decision pages
(one page per record file, each with its stamp; a roadmap page only when the roadmap file exists). It does not
read the views, the record or the declarations, and it does not count diagrams. `check_views` and the browser check
are not run in this mode (the Action skips them). A browser check for decisions mode is an open follow-up, due before
the first decisions-only portal is published. `check_decision_indexes` runs as in full mode, except that checks 1,
3 and 4 do not run when `decisions.index.register` is `none`.

## `check_export_browser.mjs`: the file in a browser

```
node arch_kit/tools/export/check_export_browser.mjs FILE --shots DIR [--puppeteer-config FILE]
```

It opens the file in headless Chrome (from `PUPPETEER_EXECUTABLE_PATH`), takes screenshots into `--shots`, and checks
browser state, not words on the page:
- that the buttons work;
- that the pages are present;
- that the diagrams are drawn with real size;
- that the counts match.

Run `npm ci` in `arch_kit/tools/export` first.

## Names in the published file

A project keeps two lists of its own. Both stay out of the kit, and out of any public repository.

- **Relabel list:** one rule per line. Each rule is a regular expression, a TAB, then the replacement. Lines starting
  with `#`, and blank lines, are ignored. `render_html --relabel` applies the list to the decision records as they
  load, then to the whole finished HTML: text between tags, and the shown attributes (`title`, `alt`, `aria-label`,
  `placeholder`, `content`, `data-title-*`). It never rewrites an `id`, an `href`, a `class` or another `data-*`
  value, nor a script, a style or a comment. The source files are not changed. `check_export --relabel` fails if
  anything the rules should have replaced is still in the file.
- **Barred list:** one pattern per line, with an optional `|reason` after it. `check_export` and the `quotes` rule
  fail on any match. `render_html --barred` applies it to the finished HTML.

The leak scan runs in the render, on the finished HTML: a relabel survivor (for example a name that reached an `id`),
or a barred value when `--barred` is given, is exit 1 and no file is written. The message names the rule number and a
count, never the value. `check_export` repeats both scans as the independent check.

When the declaration says `portal.audience: public`, a missing list is an input error (exit 2), before any work:
`check_export` needs at least one `--relabel` (it always needs `--barred`), and `render_html` needs at least one
`--relabel` and at least one `--barred`. The rule asks that a list is given, not that it is private: the sample lists
satisfy it.

Public CI uses the sample lists by design. A project's real lists stay out of its public workflows, secrets included,
so the relabel with the real names runs only locally, where the project's private list is. A CI pass is therefore
never a real-name check, and is never reported as one.

The kit ships `relabel-sample.txt` and `barred-sample.txt`, with made-up entries, so that its tests and a first run
have something to read. A green run with the samples shows the mechanics work. It is not evidence that a project's
private list ran.
