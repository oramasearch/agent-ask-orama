# CLAUDE.md — agent-ask-orama

Ask Orama, the general agent for all of lake. Read the zetta-bridge `CLAUDE.md` (*Agents in lake*)
and `docs/agents/scaffold.md` first; the org rules in `oramasearch/orama-bridge` `CLAUDE.md` apply.

- **As the person, never more.** Every call carries the key lake delegates for the turn. Never add
  a credential of its own.
- **It never writes.** A change is a proposal the person confirms in lake. A tool that writes
  directly is a defect, whatever it would save.
- **Delegation goes through lake** (`agent_turn`), never to another agent's pod.
- **The vocabulary is derived** from lake's OpenAPI at every turn; never hand-write a capability list.
- **App and build facts are live.** Read App and build state with their retained events. Building
  or changing an App goes to `agent-application` as an `app` turn. App actions stay proposals.
- **Training experiments go to Experiments Agent.** Design uses an `experiment` turn, live progress
  uses `experiment_status`, and results or divergence use `experiment_explain`. Ask Orama reports
  the proposal or result; only lake can forward a person's confirmed proposal or promotion.
- **Evals and training corpora go to the agents that make them** (agent-ask-orama#28): an eval to
  `agent-eval-generator` (Eval Generator Agent), a training corpus to `agent-autosuggest-corpus`
  (Auto-Suggest Corpus Agent) or `agent-project-corpus` (Project Corpus Agent). Agents are named
  as lake#763 names them.
- **Solution facts are live.** Read `list_solutions` on every solution turn, then `get_solution` or
  the Project's policy, experiment, ledger, monitor and measured readout. Propose policy changes;
  never apply them. Never promise returns, prices or odds.
- **Evals are generated and graded by rules** (`evals.py`), run against a real lake; a score not
  produced by the runner is not a score. A prompt change is a new `prompts/vN.md`.
- uv, never pip. Private repo, private image (`oramasearch/agent-ask-orama`).
