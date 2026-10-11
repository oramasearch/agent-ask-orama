# Solution support

Ask Orama treats the workspace engine's solution registry as live data. A solution is a catalogue
module that composes methodologies into a Pipeline and connects it to a decision policy, holdout,
actions and measured readout.

For every turn about the catalogue or a solution Project's policy, experiment, ledger, monitor or
measured readout, prompt v6 first reads:

```json
{
  "customer_id": "<current space>",
  "capability": "list_solutions",
  "input": {}
}
```

The call uses lake's read-only `workspace_query`, also on a lake that names every engine
capability (lake#650): lake's own `list_solutions` and `get_solution` add the workspace's own
solutions to the catalogue and are not the registry. Ask Orama does not carry catalogue entries in its
prompt and does not reuse a result from an earlier turn. It uses `get_solution` for the current
details of an entry and describes the fields the engine returns, including its product copy, use
case, methodology composition, declared levels, actions, latency, autonomy, data roles, status,
missing foundations and tracking issue.

## Availability and creation

The catalogue distinguishes three states:

- A runnable entry can be proposed at one of its declared levels.
- A non-sketch entry with missing production foundations can still build its composed Pipeline.
  Ask Orama calls it a preview and says “the pipeline builds; production operation needs …” with
  the returned components and issues. It does not present the solution as production-ready.
- An entry with `status: "sketch"` cannot be built. Ask Orama gives its promotion condition and
  issue instead.

Creation is a proposal for the person to confirm. Since prompt v11 it is `compose_solution`
(lake's name for the engine's `create_solution`, with the same fields at the top level); on an
older lake, the `workspace_act` form:

```json
{
  "customer_id": "<current space>",
  "capability": "create_solution",
  "input": {
    "project": "retention",
    "solution": "S-1",
    "level": 1,
    "sources": {
      "source": "datasets",
      "table": "customers"
    }
  }
}
```

The handler independently requires a `list_solutions` result from the current turn before known
solution reads and state-changing operations. For creation, it refuses unknown entries, sketches
and levels the returned entry does not declare. It does not reject a non-sketch solely because
`runnable` is false: the missing-component list governs the preview warning. These checks apply to
both forms (`compose_solution` and `workspace_act` / `create_solution`). `run_solution` is also a
proposal; Ask Orama never runs it directly.

## Policy and evidence reads

After the registry read, Ask Orama uses the current engine operations, by lake's name where lake
has one (prompt v11) or through `workspace_query`:

- `get_policy` reads the Project's active decision policy.
- `get_holdout_experiment` (the engine's `get_experiment`) reads its holdout; lake's own
  `get_experiment` is a training experiment and is not a solution read.
- `list_ledger` reads score → decision → action → outcome evidence.
- `get_monitor` reads its monitor.
- `get_roi_readout` reads measured value.

An `unknown_capability` response means that operation is not deployed yet. It is reported as such,
not as an empty policy or an empty measurement. Ask Orama reports only returned measurements and
never promises return figures, pricing or odds of success.

Policy edits, decisions and approvals change state. Ask Orama records them as proposals (the named
capability, or `workspace_act` on an older lake) with an impact statement; no write is sent before the person confirms in lake.

## Older engines

If `list_solutions` returns `unknown_capability`, the workspace predates the solution registry.
Ask Orama says the catalogue and solution operations are not deployed and falls back to the live
methodology registry when methodologies can answer the question.

## Verification

The unit tests use a fake lake and Zetta response for a runnable S-1 entry, a buildable S-2 preview
with missing policy and readout foundations, a refused B-1 sketch, an older engine, all requested
policy and evidence reads, an unavailable operation, and a policy proposal that never reaches the
write endpoint. The live eval runner grades S-1 and B-1 against the registry it reads at run time
and requires `get_roi_readout` for a measured-readout request.
