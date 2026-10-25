# Documentation

- [`releases/`](releases/) — one page per release, newest first; the version is
  `pyproject.toml`'s and `tests/test_release.py` holds the page to it.

- [`agents/`](agents/) — Design → Agents designs an agent (and the Agent Factory), Train → Agents
  trains one that learns (lake#653); the agent pages a turn is asked from, and their evals; evals
  and training corpora handed to the Eval Generator, Auto-Suggest Corpus and Project Corpus Agents
  (agent-ask-orama#28).
- [`capabilities/`](capabilities/) — the capability index from lake's OpenAPI, every workspace
  engine capability by its own name (lake#650), the older-lake fallback and the named list of
  ceremonies never offered.
- [`reads/`](reads/) — what one read hands the model: a long list trimmed by its items with its
  exact count, paged answers, and the said cut of last resort (agent-ask-orama#21).
- [`apps/`](apps/) — live App and build status, retained events, Application Agent delegation and
  proposal-only actions.
- [`experiments/`](experiments/) — Experiments Agent routing for study design, progress and
  explanations, plus the lake-owned confirmation path.
- [`models/`](models/) — `compare_models` for "which model scored best" (held-out scores in one
  read), and how a turn that runs out of tool rounds ends as failed with an honest partial answer.
- [`methodologies/`](methodologies/) — how Ask Orama discovers and enforces the engine's current
  methodology support, and how it drafts a workspace methodology's files (lake#688).
- [`solutions/`](solutions/) — live solution discovery, preview and sketch handling, policy and
  evidence reads, proposal enforcement and older-engine behavior.
- [`how-to/`](how-to/) — questions about using Lake answered from Lake's Docs: the exact page
  path, linked, and only the formats a guide states (prompt v14, lake#817).
- [`quickstart/`](quickstart/) — the Quickstart's model step (lake#1182): the dataset named by the
  page, ideas first, the strongest model proposed as `train_quickstart`, a corpus only when nothing
  else fits (prompt v16).
- [`mcp/`](mcp/) — the workspace's connected MCP tools, read as data, changes proposed (lake#652).
- [`proposals/`](proposals/) — a proposal names only a project that exists, a new project is one
  `compile_pipeline` with `create_project`, and Lake's record of each earlier proposal decides the
  next turn (prompt v15, lake#1193, lake#1194).
