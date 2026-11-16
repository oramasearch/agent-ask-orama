# Methodology support

Ask Orama treats the workspace engine's methodology registry as live data, not prompt knowledge.
For a question about what Orama can do, a Pipeline methodology change, or a Pipeline that trains
nothing, prompt v5 starts the turn with:

```json
{
  "customer_id": "<current space>",
  "capability": "list_methodologies",
  "input": {}
}
```

Since prompt v11 the call is lake's named `list_methodologies`, or the same call
through the read-only `workspace_query` on an older lake; the registry is recorded from either.
The result supplies each methodology's identifier, name, family, model kinds, solutions, required inputs, outputs, metrics, `runnable`,
`partial` and tracking `issue`. Ask Orama answers support questions from those fields and converts a
`zetta#N` issue into its GitHub link.

## Pipeline changes

For a runnable methodology, Ask Orama may propose `compile_intent` (or `workspace_act` /
`compile_intent` on an older lake) with the
project, intent and explicit `methodology`, or delegate an existing Pipeline to `agent-project`
with its project and graph context. The person still confirms every proposal in lake.

The tool handler independently checks every methodology identifier nested in a proposal. It records
the registry result only for the current turn. A proposal is rejected before it reaches lake when:

- the turn has not read `list_methodologies`;
- the identifier is missing from the current registry; or
- the registry entry has `runnable: false`.

An unsupported entry is returned as `not_supported` with its registry issue. Ask Orama does not
offer a generic Pipeline as a substitute. A `partial: true` methodology can be proposed only when
it is also runnable, and the answer explains the partial limitation.

## Older engines

If `list_methodologies` returns `unknown_capability`, the workspace predates the registry. Ask Orama
uses the compatibility rule supplied by Zetta: only M-1 churn / GBDT classification runs. It says
that explicitly and refuses proposals for other methodology identifiers. Registry availability for
that engine generation is identified as `zetta#1061`.

## Pipeline and feature explanations

For a Pipeline that appears to train nothing, Ask Orama reads `get_pipeline` (the engine's
`get_graph`) or `get_project` and
explains its `methodology` and `runnable` values. It can use `analyze_dataset` for semantic types,
grain, keys, joins and leakage suspects, then `plan_features` with a runnable methodology for the
feature plan or the required transformation.

## Verification

The unit tests fake lake and Zetta responses for a runnable M-3 registry entry, an unsupported M-14
entry with its issue, and an old engine's `unknown_capability` response. The live eval runner adds
fixed questions for customer segmentation and speech analytics and grades the answers against the
registry it reads at run time.

## Drafting a workspace methodology

Lake's Design → Methodologies → New methodology drawer has an **Ask Orama** button. It sends Ask
Orama a `methodology_draft` turn through `agent_turn` (lake's agent bus, like every library-agent
turn): the person's description as the message, and `context` with the `name` and `target_kind`
they chose. That turn is not a conversation: `service.run_turn` hands it to
`methodology_draft.py`, which answers the three files of a methodology
(lake `docs/api/methodologies.md`):

- `methodology.json`: the manifest the model wrote, with `interface: 1`, `entrypoint:
  methodology.py` and `packages: requirements.lock` set by the agent;
- `methodology.py`: `fit`, `predict` and `score` (and `explain` when declared) at module level;
- `requirements.lock`: empty for the standard library (what the prompt prefers), or each package
  the model pinned (`name==version`, every dependency listed, as they install with `--no-deps`)
  followed by `--hash=sha256:` for **every wheel the Python package index has for that version**.
  The model never writes a hash; `pypi_wheel_hashes` reads them from
  `https://pypi.org/pypi/<name>/<version>/json`. A pin the index does not have, or that has no
  wheels, is a finding.

Before answering, the draft is checked the way Lake's Validate checks code without running it:
the manifest's fields (`check_manifest`: name, input kinds, target and `required`, metrics,
parameters with defaults inside their bounds or choices), `fit`/`predict`/`score` defined at
module level (`check_entrypoint`, parsed, never imported), and the lock. A draft that fails gets
one more model round with the failing findings; one that still fails answers `ok: false` with
`findings`, which lake's bus records as `failed`, and Lake offers its own template instead.

A passing draft is `{ok: true, reply, result: {kind: "methodology_draft", name, reason, files,
findings, prompt_version}}`. Lake reads it with `draft_methodology {task_id}`, checks the files
again with its own manifest, entrypoint and lock checks (its checks are the authority), and only
then offers it in the drawer for review. Nothing is written until the person presses Create.

The prompt is `prompts/methodology_draft_v1.md`. The model is reached through lake's model gateway
with the turn's own key, as for every turn, so its tokens are counted in the workspace.
