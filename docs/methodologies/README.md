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

Since prompt v11 the call is lake's named `list_methodologies` (lake#650), or the same call
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
