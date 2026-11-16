# Prompts

Each prompt behavior change creates a new version; previous versions remain for trace history.
`agent.py` selects the active version through `PROMPT_VERSION`.

- `methodology_draft_v1.md` is the `methodology_draft` turn's own prompt (lake#688,
  `methodology_draft.py`, `DRAFT_PROMPT_VERSION`): the manifest, the fit/predict/score interface
  and the Data object, standard library preferred, pins without hashes (the agent looks them up).
- `v17.md` is `v16.md` plus following the Quickstart after a confirm: Lake's page now
  says where the Quickstart is (`quickstart_state`: deciding, training, failed, trained or done;
  `model`, `model_problem`, `quickstart_next`). After a confirm it says what started and what comes
  next, never "Done: train_quickstart"; asked about progress it reads `quickstart_status` in the
  turn; after a failure it says why in the person's words and proposes the corrected change as a
  `train_quickstart` card; it never tells the person to "configure" an internal setting (graph
  hints, a K range, a holdout). `agent.py`'s `quickstart_text` gives each state its own direction.
- `v16.md` is `v15.md` plus the Quickstart: it answers a turn from Lake's Quickstart model step (lake#1182; the turn's `page` has
  `quickstart_id`, `dataset`, `dataset_path`, `rows`, `columns`, `predictable_columns`,
  `search_index`): the dataset is known, so it never asks which one; it leads with ideas (a
  yes-or-no model, a derived target, M-3 clustering, Auto-Suggest opportunities, an analysis, an
  Application Agent app such as a dashboard), proposes the strongest model as `train_quickstart`
  so one Confirm starts it, proposes bundles as separate proposals, and offers a generated corpus
  only when nothing else fits or the person asks. Outside the Quickstart too, "what could I build?"
  is answered with ideas, never routed to a corpus agent. `agent.py`'s `quickstart_text` adds the
  same direction to the turn.
- `v15.md` proposes only what can work: a project a proposal names must
  exist (read `list_projects` first; lake and the agent both refuse one that does not); a new
  project's pipeline is one `compile_pipeline` with `create_project: true`; and lake's record of
  each earlier proposal (`pending`, `confirmed`, `failed`, `withheld`) is the truth, so after a
  failure "create it then" gets a new, corrected proposal, never a pointer to the failed one
  (`docs/proposals/`).
- `v14.md` answers questions about using Lake from Lake's Docs (`list_docs`, then `get_doc`):
  pages, tabs and buttons named exactly as the guide and the navigation show them and linked, and
  only the formats and limits the guide states; "Lake Console" is the product, not a page
  (lake#817, `docs/how-to/`).
- `v13.md` hands an eval to `agent-eval-generator` (Eval Generator Agent) and a training corpus to
  `agent-autosuggest-corpus` (Auto-Suggest Corpus Agent) or `agent-project-corpus` (Project Corpus
  Agent), asking which agent the corpus trains when the person does not say, and uses lake#763's
  agent names throughout: Project Agent, Application Agent, Experiments Agent, Auto-Suggest Agent,
  Agent Creator Agent (agent-ask-orama#28; lake lists all nine as ordinary agents).
- `v12.md` names Design (projects, Pipelines, solutions, agents) and Train (agents to train, runs,
  experiments, models), sends a new agent to Design → Agents or the Agent Factory and improving one
  to Train → Agents, and speaks of designing an agent on `/design/agents` and `/design/agent` and of
  training it on `/train/agents` and `/train/agent`.
- `v11.md` drops the hand-kept engine reads and the `workspace_query` / `workspace_act` form
  wherever lake names the engine capability itself: workspace data is read and proposed
  by its own name from the live lists, with a line for an older lake; the solution registry stays
  the engine's `list_solutions` through `workspace_query`; solutions are composed with
  `compose_solution` and their holdout read with `get_holdout_experiment`.
- `v10.md` adds `compare_models` for "which model scored best" (held-out scores of every model in
  one call), the `limit` and `id`/`run_id` inputs of the run and model reads, and what to say when
  the turn's tool rounds run out.
- `v9.md` stops offering the corpus and eval generators for delegation (reversed in
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
