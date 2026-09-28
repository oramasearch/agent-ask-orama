# CLAUDE.md — agent-ask-orama

Ask Orama, the general agent for all of lake. Read the zetta-bridge `CLAUDE.md` (*Agents in lake*)
and `docs/agents/scaffold.md` first; the org rules in `oramasearch/orama-bridge` `CLAUDE.md` apply.

- **As the person, never more.** Every call carries the key lake delegates for the turn. Never add
  a credential of its own.
- **It never writes.** A change is a proposal the person confirms in lake. A tool that writes
  directly is a defect, whatever it would save.
- **Delegation goes through lake** (`agent_turn`), never to another agent's pod.
- **The vocabulary is derived** from lake's OpenAPI at every turn; never hand-write a capability list.
- **Solution facts are live.** Read `list_solutions` on every solution turn, then `get_solution` or
  the Project's policy, experiment, ledger, monitor and measured readout. Propose policy changes;
  never apply them. Never promise returns, prices or odds.
- **Evals are generated and graded by rules** (`evals.py`), run against a real lake; a score not
  produced by the runner is not a score. A prompt change is a new `prompts/vN.md`.
- uv, never pip. Private repo, private image (`oramasearch/agent-ask-orama`).
