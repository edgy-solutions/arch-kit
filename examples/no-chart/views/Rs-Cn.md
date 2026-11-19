# Resources-Connectivity (Rs-Cn)

Which resource talks to which. A locker takes a parcel at the kerb and holds it. The depot sends it on by size class.

| From_resource | To_resource | What_moves_between | Link_state_required | Pick_method_used | Batch_size_limit | Send_interval_hours | Sender_role_on_site | Fallback_when_link_cut |
|---|---|---|---|---|---|---|---|---|
| Locker | Depot | Parcels | Link_up | Kerb_scan | Batch_of_ten | Every_hour | Locker_clerk | Held_in_the_locker |
| Depot | Van | Parcels | Always | Size_class | One_van_load | On_departure | Depot_clerk | Held_at_the_depot_bay |
| Van | Locker | Empty_crates | Always | Crate_tag | One_crate | Daily_round | Driver | Left_at_the_next_site |
| Locker | Clerk | Fault_notes | Link_up | Door_sensor | One_note | On_fault | Locker_clerk | Kept_on_the_locker |
| Clerk | Depot | Repair_orders | Link_up | Fault_note | One_order | On_request | Depot_clerk | Queued_at_the_depot |

## Exceptions

| Exception | Where | Why |
|---|---|---|
| None declared | Whole view | The views are written from the decision records, so nothing is held back |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The locker and depot flows | [Roadmap note](../decisions/ROADMAP.md) | Decision pending | Declared |
