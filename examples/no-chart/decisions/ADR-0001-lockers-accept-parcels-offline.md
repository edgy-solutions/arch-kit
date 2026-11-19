# ADR-0001 Lockers accept parcels offline

## Status

Accepted.

## 1. Decision

A locker takes in a parcel and gives the sender a receipt without a link to the depot. The locker keeps the parcel's
record until the link returns, then sends it on.

## 2. Offline behaviour

With the link down, the locker still accepts parcels until its bays are full. It refuses the next one and says why.

## 3. Consequences

The depot learns of a parcel later than the sender does. A receipt is not proof that the depot has the record.

The first locker built to this decision was Pylon-12, and its receipts were the model for the rest.
