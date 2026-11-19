# Design record: the flow record

**Status: proposed, with proposed answers to its questions, pending the project owner's ruling. FL-1 to FL-3 are
built on branch feat/flow-records, pending the ruling.**

Proposes a decision: the kit gets a flow record. One flow says that one part of a project sends one kind of record to
another part, over one channel, and which decision records decided it. A project declares its flows as data. The
export lists them, shows them on the pages of the decisions and capabilities they touch, and counts the ones that are
not built or that no decision covers.

## 1. Why a record, and not only a reader

Today the kit learns a project's flows from one reader, `exchange: {reader: helm-annotations}`. It reads one
platform's chart shape: named ConfigMaps and workloads, one broker StatefulSet per tier, and `broker/topic`
annotations. A project whose chart is shaped differently, or that has no chart, cannot declare a flow at all.

A flow record is written by hand, in the project's own repository, like a decision record. It needs no chart and
no reader. It can record a flow before it is built.

## 2. The shape

```yaml
flows:
  - id: FL-001
    from: intake            # a part of the project, or capability:<name>
    to: depot
    carries: parcel.v1      # the schema key of what is sent
    via: "broker/parcels"   # a topic, a queue or an API path
    decided_by: [ADR-0001]  # the decision records that decided it; may be empty
    built: false
```

- **All seven keys are required.** No other key is accepted.
- **`id`** is `FL-` then capitals, digits and hyphens (for example `FL-001` or `FL-TRACE`) and is unique in the
  project. An id carries no project-name prefix, because a composed build renders each member's flows under that member.
- **`from` and `to`** name a part of the project, in the project's own words, or `capability:<name>`. They must
  differ.
  - The kit keeps no list of a project's parts, so a part's name is not checked against anything.
  - A `capability:` name must exist in the project's capability record. A decisions-only project has none, so it
    cannot use the form.
- **`carries`** is the schema key, with no whitespace.
- **`via`** is one line.
- **`decided_by`** lists local decision ids, or `<prefix>:<id>` for a declared foreign prefix, as an alignment row's
  evidence does. It may be empty. An empty list is not an error, and the export counts such flows as a gap.
- **`built`** is true or false.
- **Two flows with the same `from`, `to`, `carries` and `via`** are refused as duplicates.

## 3. Where the records live

There are two routes, as for alignment records:

- `files.flows` names one YAML file, relative to `paths.root`, with no default. Its only key is `flows:`.
- The loader's `load_flows(root)` returns the same list.

Declaring both is an input error. A project that declares neither has no flows, and its export is unchanged byte for
byte.

## 4. What the export shows

- **A Flows page.**
  - It opens with a count: flows, how many are built, how many are not, and how many no decision record covers. It
    gives counts, never a percentage.
  - Then a table with one row per flow, in file order: id, from, to, carries, via, decided by and built.
  - Then a list of the flows that no decision record covers.
- **On a decision record's page,** a "Flows this record decides" list, when it decides any.
- **On a capability's page** (full mode), a "Flows" list of the flows from or to it, when there are any.
- **On the front page,** a "Flows" entry after the alignment list.

## 5. In a composed portal

Each member's flows render with that member's pages, in its own words. A composed portal does not join one
member's flows to another's: a part's name means something only inside its own project.

## 6. What this does not decide

- **Flows between projects.** A flow from one project's part to another project's part needs both names to resolve.
  It waits for a ruling on naming parts across a composition.
- **Cross-checking against the chart reader.** A project may declare both `exchange` and flow records. They render
  separately, and the kit does not compare them yet.
- **A diagram of the flows.** The page is a table.

## 7. Build steps

| Step | What | Proves |
|---|---|---|
| FL-1 | The record, both routes, and the checks | Fixture records, accepted and refused |
| FL-2 | The Flows page, the lists on decision and capability pages, the front-page entry, and an export check | An example project's golden, and existing exports unchanged |
| FL-3 | Flows in the composed build | A composed fixture with flows in two members |

## Questions for the ruling

1. **One file, or a loader** (§3)? The alternative is one file per flow, as decision records are.
2. **Parts named freely** (§2)? The alternative is a declared list of the project's parts, which every flow's `from`
   and `to` must match.
3. **May `decided_by` be empty** (§2)? If so, the export shows the flow as a gap. The alternative is that every flow
   needs a decision record.
4. **Is `built` the flow's own flag** (§2)? The alternative is to derive it from the status of the decisions in
   `decided_by`.
5. **No comparison with the chart reader yet** (§6)? The alternative is to check, now, that every flow the chart
   reader finds has a record.

## Proposed answers, pending the ruling

1. **One file, or a loader.** Flows are short. A project's flows read best as one table, and the loader route serves
   a project that keeps them elsewhere.
2. **Named freely, for now.** A list of parts is a model of a system's parts, which the kit does not have. A declared list can
   be added later without changing the record.
3. **May be empty.** A flow that runs but was never decided is exactly what the export should show. Refusing it
   would hide it.
4. **Its own flag.** A decision can be accepted before the flow it decides is built.
5. **No comparison yet.** The reader covers one platform's chart. A comparison belongs with the second reader.
