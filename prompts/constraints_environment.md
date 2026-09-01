# Constraints — Environment (this matters for how testing is structured)

- This development machine has **no network access to Databricks** — the target
  Databricks workspace/models can only be reached from the user's separate work
  computer, later. Any code path that calls a Databricks-hosted LLM or a Databricks
  SQL warehouse cannot be run or verified end-to-end here.
- Design and build everything so it is correct and ready to run once pointed at
  Databricks on the work machine, but structure tests so that everything not
  requiring a live Databricks connection (data loading/joining, deterministic
  scoring/duplication/value-realization tool logic, report rendering, graph wiring/
  routing structure) is fully testable and actually run here. Tests/paths that
  require the live LLM or live Databricks connection should be clearly separated
  (e.g. an `integration/` suite analogous to finhive's) and documented as
  "run this on the work machine" rather than silently skipped without explanation.
