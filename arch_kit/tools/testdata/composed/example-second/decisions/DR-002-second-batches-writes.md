# DR-002 The second project batches writes

Status: Adopted

## 1. Decision

Writes are grouped into batches before they reach storage.

## 2. Consequences

A crash loses at most one batch.
