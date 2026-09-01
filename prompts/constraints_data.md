# Constraints — Data

- Exactly two data sources exist, matching the two CSVs the user described (no
  separate "Lifecycle Stage Status" / "RUA Data" / "KPI" files — those concepts are
  folded into these two):
  1. **RUAI Use Case** — columns: `AI Use Case Name, count, use case id, title,
     current approved lifecycle, requested lifecycle stage, ruai approval track,
     overall use case review status, submission status detail, business owner,
     technical owner, technology owner, type of ai, technology platform`.
  2. **AI Use Case Detail** — columns: `phase id, use case, use case submission
     date, lob, sub lob, use case, use case submitter, assigned architect, ai lead
     name, use case status, current stage name, timing to get to the next stage,
     technical lead, ai developer name, business challenge, target state, comments,
     confidence level, confidence explanation, value return begins in, value return
     plateaus in, prod investment window, planned opex, scalability, current user,
     target user, insight learned or barriers, accuracy of the model, procurement
     required, max impact, min impact, planned investment, projected total
     investment, planned opex, primary impact type, secondary impact type, focus
     area, value chain, sub value chain, domain, geography, impacted business,
     impacted business detail, products`.
- No real rows are available. Generate a synthetic dataset with these exact column
  sets, large/varied enough to make every scenario in the demo (duplicates,
  underperforming value, scale candidates, discontinue candidates) actually visible
  in the data — not generic filler rows. `use case id` / `use case` (title) must
  join the two files consistently.
- The data loading layer must be written against a small storage abstraction with
  two implementations: a local one (reads the synthetic CSVs, e.g. via pandas) used
  for all development and testing on this machine, and a Databricks one (Unity
  Catalog / Delta tables via a SQL warehouse, same pattern as finhive's
  `memory/store.py`) intended for the target deployment, selected by config/env —
  mirroring how finhive's `config/settings.py` centralizes the model-tier choice.
  The Databricks implementation is written for real but cannot be exercised from
  this machine (see `prompts/constraints_environment.md`).
