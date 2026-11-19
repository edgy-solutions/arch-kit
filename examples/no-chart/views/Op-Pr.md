# Operational-Processes (Op-Pr)

What happens to a parcel, as activities.

```mermaid
flowchart LR
    a1["A1 Take in a parcel"] --> a2["A2 Send a parcel on"]
```

## Sources

The Decision column is explained under [the Decision column](../pages/reading.md#the-decision-column).

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| A1: a locker takes in a parcel | [ADR-0001 §1](../decisions/ADR-0001-lockers-accept-parcels-offline.md#1-decision) | Accepted | Built |
| A2: the depot sends a parcel on | [ADR-0002 §1](../decisions/ADR-0002-depot-routes-parcels-by-size.md#1-decision) | Proposed | Pending |
