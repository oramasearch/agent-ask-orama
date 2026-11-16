# Capabilities: what Ask Orama may name

Ask Orama hands the model few tools (`lake_read`, `lake_propose`, `compare_models`, `delegate`)
and a list of the capabilities it may name with them. The list is derived from lake's
`/v1/openapi.json` at every turn (`capability_index` in `agent.py`), never written by hand: reads
go under *Reads you may call with lake_read*, changes under *Changes you may only propose with
lake_propose* (lake's `x-lake-action`; without it, a `GET` is a read).

## Every workspace engine capability by its own name

Since lake#650 every capability of a
workspace's engine (projects, Pipelines, runs, experiments, models, search indexes, datasets,
connections, agents, solutions and decisions) is a named lake capability with its own OpenAPI
operation and input schema, the engine's fields at the top level beside `customer_id` and
`workspace_id`. They reach the index like any other capability, so Ask Orama knows all of them, not
the handful prompt v10 named. Prompt v11 drops its hand-kept list of engine reads and the
`workspace_query` / `workspace_act` form wherever a named capability exists.

- `workspace_id` is not counted as a required input: lake fills in the workspace of the turn's
  task (as it does `customer_id`, which Ask Orama sends as the person's account).
- A lake capability that serves an engine capability under another name is matched to it
  (`ENGINE_NAMES`, from lake's `docs/api/engine-capabilities.md`): `compose_solution` is the
  engine's `create_solution`, `get_holdout_experiment` its `get_experiment`, `check_pipeline` its
  `gate`, and so on. The methodology and solution checks apply to either form, so a named
  `compile_intent` still needs this turn's `list_methodologies`, and a named `compose_solution` this
  turn's solution registry and a declared level.
- Lake's own `get_experiment` (a training experiment), `list_solutions`, `get_solution` and
  `create_solution` (the workspace's own solutions beside the catalogue) are not the engine's
  (`LAKE_OWN`). The solution registry is still read as the engine's `list_solutions` through
  `workspace_query`.
- `compare_models` reads the named `list_models` when lake has it, else `workspace_query`.

### An older lake

A lake before lake#650 serves the engine only through `workspace_query` and `workspace_act`, whose
`capability` field lists no names (`older_lake`: no `enum`). There, a `lake_read` of a capability
the index lacks is sent as `workspace_query {capability, input}`, and a `lake_propose` is recorded
as `workspace_act {capability, input}`, both by the engine's name. On a current lake an unknown name
is refused as "not a lake capability" before anything is sent.

## What is never offered

`EXCLUDED_CAPABILITIES` names the ceremonies a person performs, whatever the OpenAPI lists:
signing up and in, second factors and application sign-in (`sign_in_*`, `begin_passkey_*`,
`register_passkey`, `start_oauth`, `start_sso_oidc`, `enroll_mfa`, `verify_mfa`,
`begin_application_authorization`, `exchange_application_authorization_code`); account and key
recovery (`begin_*_recovery`, `approve_admin_recovery`, `complete_*recovery`, `recover_with_code`,
`recover_repository_key`); minting credentials (the `issue_*_certificate`, `issue_*_svid`,
`issue_application_jwt` and `issue_offline_grant` capabilities, the `exchange_*_attestation`
capabilities, `mint_agent_session_key`, `mint_sealed_secret`, `rotate_identity`); and secrets in
the clear (`decrypt`, `read_secret`).

It is a list of names, not prefixes: the old `issue_` prefix also hid `issue_assignees`, the
repository read of who can be assigned an issue. A new lake capability is offered until it is
named here.

## Verification

`tests/test_agent.py` builds a current lake's OpenAPI (named engine capabilities, the `enum` on
`workspace_query` / `workspace_act`, `issue_assignees` and every excluded capability) and checks
that `issue_assignees` is in the index and no excluded capability is, that named reads are sent by
their own name, that the methodology and solution checks hold for the named forms, that an older
lake's named calls go through `workspace_query` / `workspace_act` by the engine's name, and that
prompt v11 keeps no hand-kept engine call. The eval runner adds a `workspace_entities` case
("Which training experiments, search indexes and agents do I have in this workspace?") that must
read each of the three, by lake's name or the engine's.
