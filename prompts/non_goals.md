# Non-goals

- No frontend, dashboard, or HTTP/API server of any kind — the user's team builds
  the UI themselves against the Python package directly.
- No real Databricks/Unity Catalog/ADLS/Azure Data Factory infrastructure is
  provisioned or touched from this session (no `infra/` setup scripts run against a
  real workspace) — infra code is written to the same standard as finhive's but only
  actually executed later, by the user, on the work machine.
- No conversational session memory / long-term fact memory (explicit simplification
  vs. finhive, confirmed by the user).
- No ingestion of real company data — synthetic data only, matching the given
  schemas.
- No changes of any kind to `main`, to the `finhive` package/branch, or to the
  abandoned `hackathon-insurance-portfolio` branch.
- No PDF/JSON executive report variants — Markdown only, per the user's choice.
- No production-grade integration completeness — explicitly out of scope per the
  challenge brief itself ("production-grade integrations... are not primary
  evaluation criteria for this stage").
