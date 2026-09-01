# Definition of done

- `git log`/`git branch` shows all new work committed only on
  `hackathon-ai-portfolio-intelligence`, with `main` byte-for-byte unchanged.
- Running the local test suite (the subset that doesn't require live Databricks)
  passes cleanly on this machine with `uv run pytest` or equivalent.
- A demo script/notebook runs at least 3-4 distinct scenarios end-to-end against the
  synthetic dataset and produces, for each, a concrete output artifact under
  `outputs/` — including at least one full Markdown executive report — that a reader
  can independently verify against the underlying synthetic CSV rows (i.e. every
  claim in the report is traceable to specific data, not merely plausible-sounding).
  Since the LLM itself can't be invoked from this machine, this step is verified
  structurally (graph runs, tools produce correct deterministic outputs, prompts are
  well-formed) rather than by an actual live LLM call — full end-to-end verification
  with the real LLM happens later, by the user, on the work machine.
- The golden-set evaluation harness runs locally and reports metrics (even if
  imperfect/placeholder for the LLM-dependent parts) without erroring.
- ADRs exist documenting the key architecture decisions (mirroring finhive's ADR
  convention), including explicitly *why* this differs from finhive where it does
  (no memory, storage abstraction for offline dev, package rename, domain/team
  breakdown chosen).
- README clearly explains: what the project is, how it maps to the challenge's 4
  evaluation criteria, how to run the demo, and how to point it at real Databricks
  once on the work machine.
- No hardcoded credentials anywhere; all secrets configured via `.env`
  (`.env.example` updated for this project's actual variables).
