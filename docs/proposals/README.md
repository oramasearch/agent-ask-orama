# Proposals: only what can work, and what became of each

Ask Orama never changes anything itself: a change is a proposal the person confirms in Lake. Two
defects on lake-dev (2026-10-25) showed a proposal could look valid and never work, and that after
a failed confirm the conversation could not move on. Prompt `v15` and the agent's own checks fix
both.

## What happened

Asked for a clustering pipeline, Ask Orama proposed `compile_intent` on the project "Customer
Segmentation EDA Dashboard", which did not exist; `compile_intent` only works on an existing
project. Confirming failed: *no project named 'Customer Segmentation EDA Dashboard' (or with that
id)*. The person answered "create it then", and Ask Orama replied *To create it, confirm the
proposal in Lake*, pointing at the proposal that had already failed. It kept conversations only in
memory and never learned what happened to a proposal after it was shown.

## A proposal names only a project that exists

Before `lake_propose` records a proposal whose workspace operation works on an existing project
(`compile_intent`, `capture_intent`, `compile_n8n`, `compile_python`, `import_n8n`,
`save_pipeline`, `check_pipeline`, `start_run`, `deploy_pipeline`, `approve_pipeline`,
`compile_pipeline`, `run_pipeline`, `edit_pipeline`, `create_pipeline`; `OWNING_PROJECT_OPERATIONS`
in `agent.py`), it reads the project with `get_project` as the person (`project_refusal`). A project
the read answers `not_found` for is refused in the turn, so the model corrects itself before the
person sees anything:

> FAILED: not_found There is no project named 'Customer Segmentation EDA Dashboard' in this
> workspace, so compile_intent cannot run on it; nothing was proposed. For a pipeline in a new
> project, propose compile_pipeline with {"project": ..., "intent": ..., "create_project": true} ...

A read that settles nothing (the workspace not ready) leaves the proposal to Lake, which runs the
same check when it stores the answer and withholds a proposal for a missing project
([lake docs/api/ask-orama.md](https://github.com/oramasearch/lake/blob/dev/docs/api/ask-orama.md)).

## A new project is one proposal

Lake's `compile_pipeline` with `create_project: true` creates the project (described by the intent)
and compiles its pipeline in one call, so one confirmation does both. The prompt says to propose it
for any plan that needs a new project, with `dataset` and `methodology` when known, and never
`compile_intent` for a project that does not exist. A `compile_pipeline` with `create_project` for
a project that already exists is refused (`conflict`).

## Lake's record of each proposal

Lake sends each turn `context.proposals`: the conversation's last ten proposals, oldest first, each
`{capability, input, state}` with `state` `pending`, `confirmed`, `failed` (with `error`, `code`,
`retry`) or `withheld` (with the reason). `service.py` reads it into `Turn.proposal_states`, and the
turn starts with a note of it just before the person's message (`proposal_states_text`): it is the
truth, only a `pending` proposal can be confirmed, and after a failure a request to go ahead gets a
new, corrected proposal. Because it is Lake's record, it holds after this service restarts.

If a reply still sends the person to confirm when Lake records nothing pending and the latest
proposal failed or was withheld, and the turn proposed nothing new (`points_at_nothing`), the agent
tells the model so once and lets it continue, so the turn ends with the corrected proposal:
*Here is the corrected change; confirm it below.*

## Tests

`tests/test_agent.py`: a `compile_intent` for a missing project is refused and the
`compile_pipeline` with `create_project` that follows is the only proposal recorded, each project
read first and nothing run; a new project whose name is taken is refused; a project that cannot be
read is left to Lake; malformed record rows are dropped; the stale-pointer check fires only when no
proposal waits; and the whole conversation, as the service runs it: propose, the confirm fails,
"create it then" with Lake's record, the stale reply corrected, a new valid proposal.
