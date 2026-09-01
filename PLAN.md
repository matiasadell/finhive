# Plan: Portfolio Intel — AI Portfolio Intelligence Agent

## Problem & goal

The company already has an AI Intake/approval/governance workflow, but leadership
still can't answer, from the raw governance data alone: what to prioritize, what to
scale, what's duplicative, what's failing to realize value, and where to
increase/reduce/consolidate/discontinue investment. Portfolio Intel is an agentic
decision-support layer — not a workflow replacement — that answers those questions
from the company's two AI-portfolio datasets (RUAI Use Case, AI Use Case Detail),
with every claim traceable to real data, and produces an executive-readable
recommendation report.

"Done" for this hackathon pass: a Python package (no server, no frontend) on branch
`hackathon-ai-portfolio-intelligence` that, given the synthetic dataset, runs a
hierarchical LangGraph agent end-to-end (structurally verified here; live-LLM
verified later on the work machine) across 3-4 demo scenarios, each producing a
concrete Markdown executive report under `outputs/`, backed by a golden-set
evaluation harness that runs and reports metrics without needing Databricks
connectivity. See `prompts/definition_of_done.md` for the full checklist.

## Key decisions

- **Package renamed to `portfolio_intel`**; `src/finhive/` is `git mv`'d, not
  copied, then pruned of finance-domain content. `main` and the `finhive` package
  are never touched.
- **finhive's ADRs (0001-0017) are archived, not deleted or renumbered** — moved to
  `docs/architecture/adr/finhive-legacy/` for historical reference. A fresh ADR
  sequence starts at `0001` for Portfolio Intel's own decisions.
- **One hierarchy level shallower than finhive**: the top-level supervisor routes
  directly to 4 domain ReAct agents (no per-domain sub-supervisor + multiple workers
  layer). Chosen for the 1-3 day time budget — still a genuine hierarchical
  multi-agent system (novel for this problem domain), just with one fewer tier of
  LLM calls to prompt-engineer and structurally verify blind (no local LLM access).
  Documented as an ADR with the finhive comparison made explicit.
- **Deterministic-core / LLM-narration split** (the central design bet of this
  project): every score, duplicate flag, value-realization status, and
  scale/reduce/consolidate/discontinue recommendation is computed by plain
  Python tools over the data — never invented by the LLM. The LLM's only jobs are
  routing (which agent handles a question) and turning already-computed, evidenced
  results into natural-language narrative. Consequence: prioritization quality,
  reuse identification, value realization, and explainability — the four things the
  challenge is actually graded on — are all independently testable and correct on
  this machine without ever calling a live LLM. Only routing/narration quality needs
  the work machine to verify.
- **Storage abstraction**: `PortfolioDataStore` ABC with `LocalCSVStore` (pandas,
  used here) and `DatabricksDeltaStore` (Delta via SQL warehouse, mirrors finhive's
  `memory/store.py` pattern), selected via `PORTFOLIO_INTEL_DATA_BACKEND` env var.
- **No memory/session state, no RAG, no MLflow-served Agent deployment** in this
  pass — cut straight out of the copied finhive skeleton (`memory/`, `rag/`,
  `serving/` are deleted, not adapted).
- **Report format is Markdown only**, rendered deterministically from tool outputs
  (not free LLM text) so every line is traceable to source data.
- **Evaluation metrics are computed against deterministic tool outputs**, not
  against live LLM answers — so they run and mean something on this machine, per
  the deterministic-core decision above.

# Phase 0 — Identity & scaffolding

## Task 1 — Rename package identity, prune finhive domain code, archive ADRs
**Prompts:** prompts/role.md, prompts/constraints_tech_stack.md, prompts/non_goals.md
**Context:** none
**Objective:** Turn the `finhive` checkout on this branch into an empty-but-structured `portfolio_intel` skeleton, with finhive's finance-domain content removed and its ADRs archived, ready for new content.
**Description:** Confirm `git branch --show-current` is `hackathon-ai-portfolio-intelligence` before touching anything — abort and warn if not. `git mv src/finhive src/portfolio_intel`. Inside it, delete the finance-domain-specific pieces entirely (not adapt): `agents/{crypto_alt,equity,macro,news_sentiment,portfolio_risk}/`, `tools/{crypto_data,equity_data,macro_data,news_data,portfolio_math}.py`, `memory/`, `rag/`, `serving/`. Keep (to be rewritten in later tasks, not deleted now) the shape of `config/`, `graph/`, `guardrails/`, `evaluation/`, `tools/wrappers.py`. `git mv docs/architecture/adr docs/architecture/adr/finhive-legacy` is wrong (would nest under itself) — instead create `docs/architecture/adr/finhive-legacy/`, `git mv` the 17 existing `NNNN-*.md` files into it, and leave `docs/architecture/adr/` ready for a fresh `0001-*.md` onward. Prune `notebooks/01_deploy_agent.py` (finhive Agent-deployment specific, not needed here) and `infra/databricks/{register_uc_functions.py,setup_memory_tables.py,setup_vector_search.py,setup_production_monitoring.py}` (finance/finhive-specific; a fresh minimal setup script comes later if needed, not in this task). Leave `tests/integration/*.py` in place for now (Task 14 rewrites them).
**Outputs:**
- `src/portfolio_intel/` — created via `git mv` from `src/finhive/`
- `src/portfolio_intel/agents/{crypto_alt,equity,macro,news_sentiment,portfolio_risk}/`, `src/portfolio_intel/tools/{crypto_data,equity_data,macro_data,news_data,portfolio_math}.py`, `src/portfolio_intel/memory/`, `src/portfolio_intel/rag/`, `src/portfolio_intel/serving/` — deleted
- `docs/architecture/adr/finhive-legacy/0001-*.md` … `0017-*.md` — created (moved)
- `notebooks/01_deploy_agent.py`, `infra/databricks/{register_uc_functions.py,setup_memory_tables.py,setup_vector_search.py,setup_production_monitoring.py}` — deleted
**Definition of done:** `git branch --show-current` prints `hackathon-ai-portfolio-intelligence`; `ls src/` shows `portfolio_intel/` and no `finhive/`; `ls docs/architecture/adr/` shows only `finhive-legacy/` (empty otherwise); `git log main..HEAD` and `git diff main --stat -- src/finhive` confirm `main` has no such changes (this branch's `git status` is the only place they exist).

## Task 2 — Rewrite pyproject.toml, .env.example, and config/settings.py for the new identity
**Prompts:** prompts/constraints_tech_stack.md, prompts/constraints_data.md, prompts/definition_of_done.md
**Context:** none
**Objective:** Establish the new project's package metadata and central config (model tiers + data backend selector), the single place later code imports from.
**Description:** Update `pyproject.toml`: `name = "portfolio-intel"`, description reflecting the new project, package discovery pointing at `src/portfolio_intel`; keep the same core deps (`langgraph`, `langgraph-supervisor`, `langchain`, `databricks-langchain`, `python-dotenv`, `pandas`) and drop finance-only deps if any are finhive-specific (check `pyproject.toml` as it stood before Task 1 for anything clearly finance-only, e.g. yfinance-adjacent packages — remove those; keep `databricks-sdk` for the Delta backend). Rewrite `src/portfolio_intel/config/settings.py`: keep the `get_chat_model(tier: Literal["supervisor","worker"])` factory pattern pointed at the same two Databricks Foundation Model endpoints finhive used (Llama 3.3 70B / 3.1 8B) — same tiering rationale (routing/synthesis vs. tool-calling); drop `get_router_chat_model`/AI Gateway routing split and the embeddings helpers (not used here — no RAG); add `UC_CATALOG`/`UC_SCHEMA` constants for a new schema (e.g. `workspace.portfolio_intel`) and a `get_data_backend() -> Literal["local", "databricks"]` reader of `PORTFOLIO_INTEL_DATA_BACKEND` (default `"local"`) that Task 4's storage factory will use. Rewrite `.env.example` to list exactly what this project needs (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `SQL_WAREHOUSE_ID`, `PORTFOLIO_INTEL_DATA_BACKEND`) and drop finhive-only vars (FRED/SEC/Alpha Vantage/Tavily keys).
**Outputs:**
- `pyproject.toml` — modified
- `src/portfolio_intel/config/settings.py` — rewritten
- `.env.example` — rewritten
**Definition of done:** `uv sync` (or `pip install -e .`) succeeds with the new `pyproject.toml`; `python -c "from portfolio_intel.config.settings import get_data_backend; print(get_data_backend())"` prints `local` with no `.env` present (safe default, no crash).

# Phase 1 — Data layer

## Task 3 — Canonical schema + synthetic dataset generator
**Prompts:** prompts/constraints_data.md, prompts/objective.md
**Context:** none
**Objective:** Define the exact column contracts for both datasets and generate a realistic, scenario-rich synthetic dataset from them.
**Description:** In `src/portfolio_intel/data/schema.py`, define the two column lists verbatim as given (RUAI Use Case: `AI Use Case Name, count, use case id, title, current approved lifecycle, requested lifecycle stage, ruai approval track, overall use case review status, submission status detail, business owner, technical owner, technology owner, type of ai, technology platform`; AI Use Case Detail: the full 40+ column list in `prompts/constraints_data.md`) as ordered constants (e.g. `RUAI_USE_CASE_COLUMNS`, `USE_CASE_DETAIL_COLUMNS`), so every other module imports column names from here instead of hardcoding strings. In `src/portfolio_intel/data/synthetic.py`, write a generator producing ~30-40 use cases spanning multiple LOBs/domains (insurance-plausible: Claims, Underwriting, Customer Service, Fraud, Actuarial, Marketing, IT Operations, HR) and **deliberately engineered** to make every demo scenario real in the data, not incidental: at least 3-4 pairs/clusters of near-duplicate use cases (same domain + overlapping business challenge text, different owners/LOBs — the reuse story), at least 4-5 use cases with `planned investment` far below `projected total investment` or `value return begins in` already past relative to `use case submission date` + `prod investment window` (the at-risk/off-track value story), a clear top tier of high-impact/high-confidence/high-scalability cases (the "scale these" story), and a clear bottom tier of low-impact/low-confidence/stalled-stage cases (the "discontinue" story). `use case id` must be a stable join key present identically in both files; `use case`/`title` text must match between files for the same id. Write the two generated CSVs to `data/sample_docs/rua_use_case_inventory.csv` and `data/sample_docs/ai_use_case_detail.csv`, and a short `data/sample_docs/README.md` explaining the synthetic dataset and which rows are "engineered" for which demo scenario (so the demo script and golden set can reference exact use case ids).
**Outputs:**
- `src/portfolio_intel/data/schema.py` — created
- `src/portfolio_intel/data/synthetic.py` — created
- `data/sample_docs/rua_use_case_inventory.csv` — created (generated)
- `data/sample_docs/ai_use_case_detail.csv` — created (generated)
- `data/sample_docs/README.md` — rewritten
**Definition of done:** Running the generator produces both CSVs with the exact column headers from `schema.py`; `pandas.read_csv` on both, joined on `use case id`, has zero orphan ids on either side; manual inspection confirms the engineered clusters described in `data/sample_docs/README.md` are actually present (e.g. grep the CSV for the specific duplicate/at-risk ids named there).

## Task 4 — Storage abstraction (local + Databricks Delta)
**Prompts:** prompts/constraints_data.md, prompts/constraints_environment.md
**Context:** none
**Objective:** Give the rest of the system one data-access interface that works identically whether the demo runs locally (this machine) or against real Databricks (work machine).
**Description:** In `src/portfolio_intel/data/store.py`, define an ABC `PortfolioDataStore` with methods to load the two datasets as pandas DataFrames (or a joined view — pick whichever the tools in Phase 2 will find more natural, but keep both raw-per-file access and a joined `get_use_cases()` convenience method) plus a `load_portfolio_data() -> PortfolioDataStore` factory in the same file that reads `get_data_backend()` from `config/settings.py` and returns `LocalCSVStore(...)` (reads the two CSVs from `data/sample_docs/`) or `DatabricksDeltaStore(...)` (executes SQL against the SQL warehouse via `databricks.sdk.WorkspaceClient`, same `execute_sql` pattern as finhive's old `memory/store.py` — two Delta tables under `UC_CATALOG.UC_SCHEMA`, e.g. `rua_use_case_inventory` and `ai_use_case_detail`, read into DataFrames). `DatabricksDeltaStore` is written for real (correct SQL, correct auth pattern) but cannot be run from this machine — do not skip implementing it, just don't expect to verify it here. All Phase 2 tools depend only on `PortfolioDataStore`'s interface, never on `LocalCSVStore`/`DatabricksDeltaStore` directly, so nothing downstream needs to change when the backend switches.
**Outputs:**
- `src/portfolio_intel/data/store.py` — created
**Definition of done:** With `PORTFOLIO_INTEL_DATA_BACKEND` unset (defaults to `local`), `load_portfolio_data().get_use_cases()` returns a DataFrame with one row per use case id, columns from both source files present, matching the row count of the synthetic CSVs from Task 3.

# Phase 2 — Deterministic domain tools

## Task 5 — Prioritization scoring tools
**Prompts:** prompts/objective.md, prompts/definition_of_done.md
**Context:** none
**Objective:** Deterministic, explainable composite priority score per use case.
**Description:** In `src/portfolio_intel/tools/prioritization_tools.py`, implement a pure function `compute_priority_scores(df) -> DataFrame` adding a `priority_score` column (0-100) as a weighted composite of: impact (from `max impact`/`min impact`, normalized across the portfolio), confidence (`confidence level` mapped Low/Medium/High → numeric), investment efficiency (impact per dollar of `projected total investment`), stage proximity (`current stage name` mapped to how close it already is to production/value — later stages score higher), and `scalability` (Low/Medium/High → numeric). Pick specific weights, document them in a module docstring with the rationale (this is the explainability backbone — the weights themselves must be stated, not hidden). Add `get_top_priorities(df, n) -> DataFrame` and `explain_priority_score(df, use_case_id) -> str` (renders the exact component values and weights that produced that use case's score — this is what the LLM will be given verbatim to narrate, never asked to compute itself). Wrap all three with `safe_tool` (carried over from finhive's `tools/wrappers.py`, kept as-is) and expose as LangChain tools the same way finhive's workers did (`tool(safe_tool(fn))`).
**Outputs:**
- `src/portfolio_intel/tools/prioritization_tools.py` — created
**Definition of done:** Unit test (Task 14 writes the full suite, but sanity-check now) confirms the engineered "top tier" use cases from Task 3 score above the engineered "bottom tier" ones, and `explain_priority_score` output contains the actual numeric field values used, not just the final score.

## Task 6 — Reuse & duplication detection tools
**Prompts:** prompts/objective.md
**Context:** none
**Objective:** Surface likely-duplicate/overlapping use cases with concrete evidence.
**Description:** In `src/portfolio_intel/tools/duplication_tools.py`, implement `find_duplicate_use_cases(df, similarity_threshold=0.4) -> list[dict]`: group candidates by shared `domain`/`value chain`/`sub value chain`/`focus area`, then score textual overlap between `business challenge` (+`target state`) fields using a simple, dependency-light method (token-set Jaccard similarity on lowercased/stopword-stripped text is enough — no embeddings/vector search needed here, that's a Databricks-only concern out of scope per non-goals) — pairs above the threshold are returned with both use case ids, the shared dimensions, the similarity score, and the actual text snippets that matched (again: this becomes the LLM's evidence, not something it infers). Add `get_use_case_overlap_detail(df, use_case_id) -> list[dict]` for "what overlaps with this one specifically" queries. Wrap with `safe_tool`.
**Outputs:**
- `src/portfolio_intel/tools/duplication_tools.py` — created
**Definition of done:** Running against the Task 3 synthetic data, `find_duplicate_use_cases` returns exactly the engineered duplicate clusters documented in `data/sample_docs/README.md` (no more, no fewer, modulo the threshold being reasonable) — this becomes a golden-set check in Task 13.

## Task 7 — Value realization tools
**Prompts:** prompts/objective.md
**Context:** none
**Objective:** Flag use cases not on track to realize their promised value, with the specific evidence.
**Description:** In `src/portfolio_intel/tools/value_realization_tools.py`, implement `compute_value_realization_status(df) -> DataFrame` adding a `value_status` column (`on_track` / `at_risk` / `off_track`) per use case, derived from: cost variance (`planned investment` vs `projected total investment`/`planned opex`), timeline variance (`use case submission date` + `prod investment window` vs `value return begins in`/`value return plateaus in` — is it already past when value was supposed to start, given its `current stage name`?), and qualitative risk signals (`confidence level` low, non-empty `insight learned or barriers` mentioning a blocker). Add `get_at_risk_use_cases(df) -> DataFrame` and `explain_value_status(df, use_case_id) -> str` (same evidence-rendering pattern as Task 5). Wrap with `safe_tool`.
**Outputs:**
- `src/portfolio_intel/tools/value_realization_tools.py` — created
**Definition of done:** The engineered "at-risk/off-track" use cases from Task 3 come back flagged as `at_risk`/`off_track`; the engineered healthy ones come back `on_track`.

## Task 8 — Portfolio recommendation synthesis tool
**Prompts:** prompts/objective.md, prompts/definition_of_done.md
**Context:** none
**Objective:** Turn priority/duplication/value signals into one concrete scale/reduce/consolidate/discontinue recommendation per use case, with evidence.
**Description:** In `src/portfolio_intel/tools/recommendation_tools.py`, implement `generate_portfolio_recommendations(df) -> list[dict]` that calls the Task 5-7 functions internally and applies an explicit rule table (document it in the module docstring) mapping `(priority_score tier, value_status, has_duplicate)` combinations to one of `Scale`, `Continue/Monitor`, `Consolidate`, `Reduce Investment`, `Discontinue` — e.g. high priority + on_track + no duplicate → Scale; any use case with a duplicate above the reuse threshold → Consolidate (regardless of its own score) with the specific overlapping use case id named; low priority + off_track → Discontinue. Each returned recommendation dict carries the action, a short reason string built from the actual component values (not templated filler), and references to the specific evidence (score breakdown, duplicate match, value status) so the report generator (Task 11) never has to re-derive anything. Wrap with `safe_tool`.
**Outputs:**
- `src/portfolio_intel/tools/recommendation_tools.py` — created
**Definition of done:** Every use case in the synthetic dataset gets exactly one recommendation; spot-check that the engineered scenarios (duplicate cluster, at-risk cases, top/bottom tiers from Task 3) map to the expected action.

# Phase 3 — Agentic graph

## Task 9 — Graph state + 4 domain ReAct agents
**Prompts:** prompts/constraints_tech_stack.md, prompts/objective.md
**Context:** none
**Objective:** Wrap each Phase 2 toolset in a ReAct agent with a domain-scoped prompt, mirroring finhive's worker pattern but one tier shallower (see Key decisions).
**Description:** In `src/portfolio_intel/graph/state.py`, define `PortfolioState(MessagesState)` with an `iterations` counter (same safety-cap purpose as finhive's `FinHiveState`) — no `next`/memory fields needed beyond what routing requires (decide alongside Task 10). In `src/portfolio_intel/agents/{prioritization,reuse_duplication,value_realization,portfolio_recommendation}.py`, build one `create_agent(...)` ReAct agent per domain (same `langchain.agents.create_agent` call finhive used), each given only its own Phase 2 toolset, with a system prompt that explicitly instructs it to **only state numbers/evidence that came back from a tool call** — never compute or estimate a score, duplicate match, or recommendation itself. Use `get_chat_model("worker")` for these four (they're tool-calling agents, not routers/synthesizers — same tiering rationale as finhive).
**Outputs:**
- `src/portfolio_intel/graph/state.py` — created
- `src/portfolio_intel/agents/prioritization.py` — created
- `src/portfolio_intel/agents/reuse_duplication.py` — created
- `src/portfolio_intel/agents/value_realization.py` — created
- `src/portfolio_intel/agents/portfolio_recommendation.py` — created (its agent has access to the Task 8 tool, which itself calls into Tasks 5-7 — this agent's tool already returns fully-synthesized recommendations, so its prompt job is purely narration over that tool's output)
**Definition of done:** Each of the 4 modules exposes a `build_*_agent()` (or equivalent) callable that returns a compiled agent; import-time smoke test (no LLM call) confirms each constructs without error given a stubbed/fake chat model (see Task 14 for the fake-model test harness).

## Task 10 — Top-level supervisor + guardrails, graph compiled end-to-end
**Prompts:** prompts/constraints_tech_stack.md, prompts/objective.md, prompts/non_goals.md
**Context:** none
**Objective:** Compose the 4 domain agents behind one routing supervisor, with input/output guardrail nodes, into a single invokable graph — no memory nodes.
**Description:** In `src/portfolio_intel/graph/top_supervisor.py`, mirror finhive's `top_supervisor.py` structure (lazy team registration dict, `_TEAM_DESCRIPTIONS` used in the router prompt to disambiguate frontier questions between the 4 domains, `_MAX_ITERATIONS` safety cap, `get_chat_model("supervisor")` for routing) but route directly to the Task 9 agents (no per-team sub-supervisor layer — the "team node" invokes the ReAct agent directly, one LLM hop shallower than finhive). In `src/portfolio_intel/guardrails/{input_guardrail,output_guardrail}.py`, adapt finhive's two guardrail nodes to this domain: input guardrail's system prompt scopes to "questions about prioritizing, scaling, deduplicating, or evaluating value realization within the company's AI use-case portfolio" (reject off-topic/prompt-injection, same as finhive); output guardrail's groundedness check looks for claims not backed by any tool-call evidence in the transcript (same rationale as finhive, adapted wording) — given the deterministic-core design, a correctly-behaving agent should almost always pass this, which is itself a useful signal if it doesn't. Wire `START → input_guardrail → supervisor → (4 agents) → supervisor → ... → output_guardrail → END` in `build_top_supervisor()` — no `memory_recall`/`memory_remember` nodes (explicit non-goal).
**Outputs:**
- `src/portfolio_intel/graph/top_supervisor.py` — created
- `src/portfolio_intel/guardrails/input_guardrail.py` — rewritten
- `src/portfolio_intel/guardrails/output_guardrail.py` — rewritten
**Definition of done:** `build_top_supervisor()` compiles without error; a structural test (Task 14, fake chat model) invokes the compiled graph with a sample question and confirms it reaches `END` within `_MAX_ITERATIONS` without exceptions, visiting at least one domain agent node.

# Phase 4 — Reporting & demo

## Task 11 — Executive Markdown report generator
**Prompts:** prompts/objective.md, prompts/non_goals.md, prompts/definition_of_done.md
**Context:** none
**Objective:** Deterministically render the challenge's "executive recommendation output" deliverable from tool outputs — independent of LLM narration quality.
**Description:** In `src/portfolio_intel/reporting/executive_report.py`, implement `render_executive_report(df) -> str` that runs the full Task 5-8 pipeline directly (not through the LLM) and renders a Markdown document with sections: Executive Summary (portfolio-level counts: how many Scale/Consolidate/Reduce/Discontinue), Top Priorities (table, with score breakdown), Reuse & Duplication (each cluster, with matched evidence), Value Realization Risks (at-risk/off-track list with evidence), and Recommendations (one row per use case: action + reason, grouped by action). This is the artifact that's independently verifiable against the source CSVs per the project's Definition of done — every number/id in it must come from Task 3's synthetic data via Tasks 5-8, nothing freeform.
**Outputs:**
- `src/portfolio_intel/reporting/executive_report.py` — created
**Definition of done:** `render_executive_report(load_portfolio_data().get_use_cases())` returns a non-empty Markdown string; manually cross-check a handful of lines against the synthetic CSV rows they cite.

## Task 12 — Demo script across multiple scenarios
**Prompts:** prompts/objective.md, prompts/constraints_environment.md, prompts/definition_of_done.md
**Context:** none
**Objective:** One runnable script demonstrating the full system across the 4 scenarios the challenge asks for ("demo different scenarios"), writing real artifacts to `outputs/`.
**Description:** In `notebooks/00_demo.py` (kept as a notebook-shaped script, same convention as finhive's, runnable both as a plain script here and later as a Databricks Repos notebook), define 4 scenario questions covering: (1) quarterly prioritization ("given limited budget, what should we prioritize next quarter?"), (2) reuse check ("is anything already in flight similar to a new proposed use case?"), (3) value realization review ("which approved use cases are not on track to realize expected value?"), (4) a cross-cutting executive ask ("give me the full portfolio recommendation"). For each, invoke the compiled graph (Task 10) and also call `render_executive_report` (Task 11) directly, writing both the raw agent transcript and the rendered report to `outputs/demo_scenario_{n}_*.md`. Since this machine can't reach Databricks, running this script here will fail at the LLM call — guard that clearly (try/except around the graph invocation with a clear printed message pointing at `prompts/constraints_environment.md`'s explanation) so the deterministic parts (data load, `render_executive_report`) still run and produce real output even without a live LLM, and the LLM-dependent part fails loudly and explains why rather than silently.
**Outputs:**
- `notebooks/00_demo.py` — created
- `outputs/demo_scenario_*.md` — created (whatever this script actually produces when run here — at least the `render_executive_report` output, given the LLM parts can't run on this machine)
**Definition of done:** Running `python notebooks/00_demo.py` locally produces the deterministic-path outputs under `outputs/` without crashing, and prints a clear, expected message (not a raw traceback) for the LLM-dependent parts.

# Phase 5 — Evaluation

## Task 13 — Golden set + deterministic metrics
**Prompts:** prompts/constraints_deadline_process.md, prompts/definition_of_done.md
**Context:** none
**Objective:** A lightweight, real evaluation harness that runs and means something on this machine, per the deterministic-core design decision.
**Description:** In `data/eval/golden_set.json`, write 8-10 scenarios, each naming specific use case ids from Task 3's synthetic data and the expected signal: e.g. `{"scenario": "duplicate_pair_1", "expect": "use_case_ids X and Y flagged as duplicates"}`, `{"scenario": "top_priority", "expect": "use_case_id Z appears in top 5 priority"}`, `{"scenario": "at_risk", "expect": "use_case_id W has value_status at_risk or off_track"}`, `{"scenario": "discontinue_candidate", "expect": "use_case_id V recommended Discontinue"}`. In `src/portfolio_intel/evaluation/metrics.py`, implement pure functions computing each check directly against Task 5-8 outputs (no LLM involved — this is the point). In `src/portfolio_intel/evaluation/run_eval.py`, load the golden set, run all checks, print/save a pass-rate summary; keep an MLflow-logging hook analogous to finhive's `run_eval.py` for later on the work machine, but make it optional/best-effort (wrapped so a missing/unreachable MLflow tracking server doesn't crash the local run — this is the one place an "LLM/Databricks-dependent path fails loudly but doesn't block the deterministic path" pattern from Task 12 repeats).
**Outputs:**
- `data/eval/golden_set.json` — created
- `src/portfolio_intel/evaluation/metrics.py` — created
- `src/portfolio_intel/evaluation/run_eval.py` — created
**Definition of done:** `python -m portfolio_intel.evaluation.run_eval` (or equivalent) runs locally, reports a pass rate, and every scenario in the golden set actually passes against the Task 3 synthetic data (if one doesn't, either the golden set's expectation or the Task 5-8 logic has a real bug — fix it, don't weaken the check).

# Phase 6 — Tests, ADRs, docs

## Task 14 — Unit tests (deterministic) + structural graph test (fake LLM)
**Prompts:** prompts/constraints_environment.md, prompts/definition_of_done.md
**Context:** none
**Objective:** Make the "runs cleanly on this machine" half of Definition of done real and automated, not just manually eyeballed during Tasks 3-13.
**Description:** Under `tests/unit/`, write tests for: `data/schema.py` + `synthetic.py` (columns match, join integrity), `data/store.py` (`LocalCSVStore` round-trip), each Phase 2 tool module (the same checks done manually per-task, now as asserts), and `reporting/executive_report.py`. Under `tests/integration/`, replace finhive's old domain-specific tests with: (a) a structural graph test using a fake/canned chat model (e.g. LangChain's `FakeListChatModel` or an equivalent stub returning scripted tool-call/structured-output responses) that exercises `build_top_supervisor()` end-to-end without any network call — this is what actually satisfies "graph runs" from the project Definition of done; (b) tests that require a live Databricks connection, clearly marked (e.g. `pytest.mark.skip(reason="requires Databricks — run on work machine")` or an env-var-gated skip) so they don't silently no-op without explanation when someone runs the suite here. Update `tests/README.md` to explain the unit vs. structural-integration vs. live-integration split and which machine each is expected to run on.
**Outputs:**
- `tests/unit/` — created (multiple files)
- `tests/integration/` — rewritten (old finhive tests removed, new structural + live-marked tests added)
- `tests/README.md` — rewritten
**Definition of done:** `uv run pytest tests/unit tests/integration -k "not live"` (or whatever marker scheme was used) passes cleanly on this machine.

## Task 15 — ADRs, README rewrite, final Definition of done pass
**Prompts:** prompts/definition_of_done.md, prompts/context.md, prompts/non_goals.md
**Context:** none
**Objective:** Document the real architecture decisions and leave the repo in a state a stranger (or the user's teammate) can pick up and understand.
**Description:** Write fresh ADRs in `docs/architecture/adr/` (starting `0001-`) for at least: the shallower one-hierarchy-level decision vs. finhive, the deterministic-core/LLM-narration split, the storage abstraction (local vs. Databricks), and the "no memory/RAG/serving" scope cut — each in finhive's ADR style (context, decision, consequences) and each explicitly cross-referencing the finhive ADR it diverges from where relevant (e.g. "unlike finhive ADR 0005, ..."). Rewrite `README.md` fully: what the project is, explicit mapping from its features to the challenge's 4 evaluation criteria (prioritization quality → Task 5/13, value realization → Task 7/13, reuse identification → Task 6/13, explainability → Tasks 5/7/8/11), how to run the demo and tests locally, and a clearly marked section on what changes to run this for real against Databricks on the work machine (env vars, `PORTFOLIO_INTEL_DATA_BACKEND=databricks`, the not-yet-executed `infra/` setup). Finally, walk the full checklist in `prompts/definition_of_done.md` item by item and fix anything not actually satisfied.
**Outputs:**
- `docs/architecture/adr/0001-*.md` … (however many are written) — created
- `README.md` — rewritten
**Definition of done:** Every bullet in `prompts/definition_of_done.md` is checked against the actual repo state (not assumed) and confirmed true; report the walkthrough result back to the user.
