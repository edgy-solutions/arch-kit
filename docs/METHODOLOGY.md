# Writing architecture records the kit can check

The kit renders and checks what a project writes. It cannot make the writing true. These rules are the ones the kit's checks assume. A record that breaks them can still pass every check, so a reviewer holds them.

## 1. Say whether a text records or proposes

Every decision record, pull request and design note opens by saying which it is.

- **Records a decision:** the decision was made, by whom it was made, and when. The text describes it, and adds nothing new.
- **Proposes a decision:** nothing is decided yet. The text names who decides, and what the decision would change.

A text that proposes must not use the words of a record ("we use", "is required"). Write "would use" or "proposed". A reader who sees only the first line must be able to tell which it is.

The record's status line carries the same word, and the kit reads it. A phase computed from a status is only as true as that word.

## 2. Findings first

Put what was found, decided or changed in the first lines. Put the method, the history and the caveats after it.

- A review starts with the defects it found, most severe first. It does not start with what was read.
- A measurement starts with the number and what it was measured on. The procedure comes after.
- If nothing was found, say so in the first line, and say what was looked at.

## 3. Read status per source

For each source a text relies on, say whether it was read, and at what version.

- **Read:** the edition, issue or commit, and the parts read (chapter, section, table).
- **Not read:** name it, and say why: paywalled, not supplied, out of scope. A source that is cited but not read is a miss, not a citation.
- **Read in part:** say which part.

A claim never rests on a source the text says was not read. When a standard sits behind a licence, cite it by clause and paraphrase it. Never copy its text or tables into a record. Value and attribute names may appear as identifiers.

## 4. Every claim cited

A claim that the architecture holds, or that a capability works, cites where that is stated or shown:

- a decision record, by section (`ADR-NNNN §LABEL`, a label that resolves to exactly one heading);
- a readiness entry, with its date and the line that shows it;
- a template or a declaration in the deployment's configuration;
- a register row, when the claim is only that the work is tracked.

The kit computes a capability's phase from these citations, and from nothing else. A description written from decisions names them in `derived_from`. When there is no source, the claim is written as a gap ("not stated") and points at the row that tracks it. Never write it as a fact.

"Declared" and "measured" are different words. A table built from a configuration render is declared, and the export says so on every page. A number is measured only when a readiness entry records the run that produced it.

## 5. Misses recorded

When a check, a review or a reading missed something, record the miss where the next reader will find it. A quiet fix is not enough.

- Name what was missed, when it was found, and what found it.
- Say which check should have caught it, and whether that check now does. If it does, a test proves it: a check that has never failed on a broken input is not yet known to work.
- Withdraw a finding that turns out wrong by striking it through and saying why. Never delete it.

## 6. Names in the published export

Write records with the names the project uses. Before an export is published, the project's relabel list replaces internal names, and its barred list fails the build on any name that must never appear. Both lists belong to the project and are never committed to a public repository. The kit runs both on the rendered file, so a name is caught wherever it came from.

A green export check run with a sample list is not evidence that the private scan ran. Say which list ran.
