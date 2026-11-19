---
title: What Woad is
kind: overview
---
Woad runs parcel lockers that keep working when the depot is out of reach.

The idea is settled in [[ADR-0001]], and the depot's half in [[other:ADR-0007]].
The locker side is [[CO-001|built]]; the depot side is [[CO-002]], which has been [[CO-002|accepted]].

| Part | Where it lives |
| --- | --- |
| locker agent | [[CO-001]] |
| depot router | [[CO-002|accepted]] |

How Woad compares with the references its owner named is in [[alignment:coverage]].

Write a citation as `[[ADR-0001]]` and the kit checks it. The same holds in a block:

```
[[ADR-0099]] is not checked here
```
