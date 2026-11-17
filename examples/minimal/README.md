# Larkspur architecture

The architecture views of the example project: a parcel-locker network, invented for the kit. A view's source is in
[views/](views/). Each ends with a Sources table that says where its claims come from.

How to read a Sources table:

| Decision | Meaning |
|---|---|
| Accepted | The record says accepted. |
| Proposed | The record says proposed. |
| Decision pending | No decision record decides it yet. |
| Generated | Computed when the view is rendered, not written in it. |

| Evidence | Meaning |
|---|---|
| Built | The record says done. |
| Declared | Read from a chart render. Nothing was observed running. |
| Pending | The record says the work is pending. |
| Not stated | The record does not say. |
| Generated | Computed when the view is rendered. |
| Status line | In the view's source only: read from the cited record's status line when the view is rendered. |
