# Prompts

Each prompt behavior change creates a new version; previous versions remain for trace history.
`agent.py` selects the active version through `PROMPT_VERSION`.

- `v10.md` adds `compare_models` for "which model scored best" (held-out scores of every model in
  one call), the `limit` and `id`/`run_id` inputs of the run and model reads, and what to say when
  the turn's tool rounds run out (agent-ask-orama#14).
- `v9.md` stops offering Orama's internal corpus and eval generators for delegation.
- `v8.md` routes study design, progress and explanations to ExperimentsAgent, summarizes proposals
  and results, and keeps confirmed study and promotion objects on lake's confirmation path.
- `v7.md` adds live App and build reads, retained event diagnosis, ApplicationAgent app turns and
  proposal-only App actions.
- `v6.md` adds a fresh solution-registry read for every solution turn, current `get_solution`
  details, honest preview and sketch language, policy and evidence reads, proposal-only policy
  changes, and the older-engine fallback to methodologies.
- `v5.md` reads the live methodology registry, declines unsupported Pipeline work with its issue,
  explains graph `methodology` / `runnable` fields, and uses the M-1-only older-engine fallback.
- `v4.md` knows the three corpus generators it can bring into a turn.
- `v3.md` maps project identifiers to names and identifies deleted projects.
- `v2.md` documents workspace data reads and the supported SQL subset.
- `v1.md` defines Ask Orama's base read, propose and delegate behavior.
