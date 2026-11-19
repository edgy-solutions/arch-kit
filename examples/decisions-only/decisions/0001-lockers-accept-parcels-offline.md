# ADR-0001 Lockers accept parcels offline

## Status

Accepted.

## 1. Decision

A locker takes in a parcel and gives the sender a receipt without a link to the depot. The locker keeps the parcel's
record until the link returns, then sends it on.

## 2. Consequences

The depot learns of a parcel later than the sender does. A receipt is not proof that the depot has the record.
