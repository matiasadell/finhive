# Constraints — Tech stack & repo placement

- Same repo as `finhive` (`https://github.com/matiasadell/finhive.git`), same git
  history — **all work happens on the already-checked-out branch
  `hackathon-ai-portfolio-intelligence`**. `main` (and the `finhive` code/branch) must
  never be modified, merged into, or rebased from this branch during this project.
- Rename the package identity away from `finhive` throughout (package dir, name in
  `pyproject.toml`, README title, Unity Catalog schema, etc.) to a name reflecting
  this project — `portfolio_intel` is the working name (confirm/refine at PLAN.md
  time if a better name surfaces, but the intent — a distinct identity from
  `finhive` — is fixed).
- Orchestration: LangGraph, same version family as finhive's `pyproject.toml`
  (`langgraph` + `langgraph-supervisor`), same ReAct pattern
  (`langchain.agents.create_agent`).
- LLM: Databricks Foundation Model APIs (native, e.g. Llama 3.3 70B / 3.1 8B), same
  tiered factory pattern as finhive's `get_chat_model(tier=...)` — this is the only
  LLM target, no alternate/local LLM provider is being built as a fallback.
- Architecture shape (hierarchical multi-team supervisor vs. a single flat
  supervisor) is Claude's judgment call — pick whichever best serves explainability
  and the four evaluation axes, and record the reasoning as an ADR the same way
  finhive does.
- No persistent conversational memory (no session/thread memory, no long-term facts
  store) — each invocation analyzes the current state of the portfolio data fresh.
  This is a deliberate simplification vs. finhive, not an oversight.
