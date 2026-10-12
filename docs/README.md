# Documentation

- [`agents/`](agents/) — Design → Agents designs an agent (and the Agent Factory), Train → Agents
  trains one that learns (lake#653); the agent pages a turn is asked from, and their evals.
- [`capabilities/`](capabilities/) — the capability index from lake's OpenAPI, every workspace
  engine capability by its own name (lake#650), the older-lake fallback and the named list of
  ceremonies never offered.
- [`apps/`](apps/) — live App and build status, retained events, ApplicationAgent delegation and
  proposal-only actions.
- [`experiments/`](experiments/) — ExperimentsAgent routing for study design, progress and
  explanations, plus the lake-owned confirmation path.
- [`models/`](models/) — `compare_models` for "which model scored best" (held-out scores in one
  read), and how a turn that runs out of tool rounds ends as failed with an honest partial answer.
- [`methodologies/`](methodologies/) — how Ask Orama discovers and enforces the engine's current
  methodology support, and how it drafts a workspace methodology's files (lake#688).
- [`solutions/`](solutions/) — live solution discovery, preview and sketch handling, policy and
  evidence reads, proposal enforcement and older-engine behavior.
- [`mcp/`](mcp/) — the workspace's connected MCP tools, read as data, changes proposed (lake#652).
