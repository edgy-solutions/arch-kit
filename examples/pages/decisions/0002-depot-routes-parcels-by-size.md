# ADR-0002 The depot routes parcels by size

## Status

Accepted.

## 1. Decision

The depot sends a parcel to a van by its size class. Large parcels go to the cargo van and small ones to the
courier bike. A parcel a locker took in offline is routed the same way once its record arrives, as ADR-0001 §2
describes.

## 2. Open question

How the depot routes a parcel whose size class is missing is not decided.

`Status: open`
**OF-1 — A parcel with no size class**

Until it is decided, the depot holds such a parcel at the bay.
