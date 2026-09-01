# Constraints — Deadline & process

- Hackathon time budget: 1-3 days total. Solo build by the user with Claude Code;
  no other reviewer. PLAN.md should be scoped so a working, demoable end state is
  reachable well inside that budget, not an open-ended finhive-scale buildout.
- Evaluation: build a golden-set + basic metrics harness analogous to finhive's
  (`data/eval/`, `evaluation/`), but keep it lightweight — a handful of representative
  scenarios with an expected recommendation/finding, and metrics that can be computed
  and reported locally without requiring a live Databricks/MLflow connection (MLflow
  logging itself can be wired the same way as finhive's for when it *is* run on
  Databricks, but the metrics computation must not depend on reaching Databricks).
