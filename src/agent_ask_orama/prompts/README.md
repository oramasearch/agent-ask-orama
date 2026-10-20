# Prompts

Each prompt behavior change creates a new version; previous versions remain for trace history.
`agent.py` selects the active version through `PROMPT_VERSION`.

- `methodology_draft_v1.md` is the `methodology_draft` turn's own prompt (lake#688,
  `methodology_draft.py`, `DRAFT_PROMPT_VERSION`): the manifest, the fit/predict/score interface
  and the Data object, standard library preferred, pins without hashes (the agent looks them up).
- `v14.md` answers questions about using Lake from Lake's Docs (`list_docs`, then `get_doc`):
  pages, tabs and buttons named exactly as the guide and the navigation show them and linked, and
  only the formats and limits the guide states; "Lake Console" is the product, not a page
  (lake#817, `docs/how-to/`).
- `v13.md` hands an eval to `agent-eval-generator` (Eval Generator Agent) and a training corpus to
  `agent-autosuggest-corpus` (Auto-Suggest Corpus Agent) or `agent-project-corpus` (Project Corpus
  Agent), asking which agent the corpus trains when the person does not say, and uses lake#763's
  agent names throughout: Project Agent, Application Agent, Experiments Agent, Auto-Suggest Agent,
  Agent Creator Agent (agent-ask-orama#28; lake lists all nine as ordinary agents, lake#788).
- `v12.md` names Design (projects, Pipelines, solutions, agents) and Train (agents to train, runs,
  experiments, models), sends a new agent to Design → Agents or the Agent Factory and improving one
  to Train → Agents, and speaks of designing an agent on `/design/agents` and `/design/agent` and of
  training it on `/train/agents` and `/train/agent` (lake#653, agent-ask-orama#19).
- `v11.md` drops the hand-kept engine reads and the `workspace_query` / `workspace_act` form
  wherever lake names the engine capability itself (lake#650): workspace data is read and proposed
  by its own name from the live lists, with a line for an older lake; the solution registry stays
  the engine's `list_solutions` through `workspace_query`; solutions are composed with
  `compose_solution` and their holdout read with `get_holdout_experiment` (agent-ask-orama#16).
- `v10.md` adds `compare_models` for "which model scored best" (held-out scores of every model in
  one call), the `limit` and `id`/`run_id` inputs of the run and model reads, and what to say when
  the turn's tool rounds run out (agent-ask-orama#14).
- `v9.md` stops offering Orama's internal corpus and eval generators for delegation (reversed in
  `v13.md`).
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
