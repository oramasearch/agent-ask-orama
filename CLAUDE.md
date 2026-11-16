# CLAUDE.md — agent-ask-orama

Ask Orama, the general agent for all of Lake. Read `README.md` and `docs/README.md` first;
`AGENTS.md` carries the conventions that apply to every change.

- **As the person, never more.** Every call carries the key Lake delegates for the turn. Never add
  a credential of its own.
- **It never writes.** A change is a proposal the person confirms in Lake. A tool that writes
  directly is a defect, whatever it would save.
- **Delegation goes through Lake** (`agent_turn`), never to another agent's pod.
- **The vocabulary is derived** from Lake's OpenAPI at every turn; never hand-write a capability list.
- **App and build facts are live.** Read App and build state with their retained events. Building
  or changing an App goes to `agent-application` as an `app` turn. App actions stay proposals.
- **Training experiments go to Experiments Agent.** Design uses an `experiment` turn, live progress
  uses `experiment_status`, and results or divergence use `experiment_explain`. Ask Orama reports
  the proposal or result; only Lake can forward a person's confirmed proposal or promotion.
- **Evals and training corpora go to the agents that make them**: an eval to
  `agent-eval-generator` (Eval Generator Agent), a training corpus to `agent-autosuggest-corpus`
  (Auto-Suggest Corpus Agent) or `agent-project-corpus` (Project Corpus Agent). Agents are named
  as Lake names them.
- **Solution facts are live.** Read `list_solutions` on every solution turn, then `get_solution` or
  the Project's policy, experiment, ledger, monitor and measured readout. Propose policy changes;
  never apply them. Never promise returns, prices or odds.
- **Evals are generated and graded by rules** (`evals.py`), run against a real Lake; a score not
  produced by the runner is not a score. A prompt change is a new `prompts/vN.md`.
- Build and test with uv, never pip: `uv sync`, then `uv run --group dev pytest`.
