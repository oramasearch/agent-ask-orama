# Apps and builds

Ask Orama treats Ship Apps and application identity pools as different resources. This behavior is
for customer-owned Ship Apps: desired application state reconciled by lake and its operator.

## Reads

The capability names and input schemas come from lake's OpenAPI on every turn. Ask Orama uses the
following reads when they are present in that live index:

- `list_apps` answers which Apps exist in the current space.
- `get_app` reads one App's desired state and observed status. Health answers use returned fields
  such as `phase`, `ready`, `message`, `url`, generation and observed generation.
- `receive_app_events` reads the retained reconciliation events for that App. Desired `running`
  state alone is not evidence that an App is ready.
- `list_builds` identifies the latest build associated with an App.
- `get_build` reads that build's phase, digest, size, message and timestamps.
- `receive_build_events` reads its retained phase, log, done and error events. `build_logs` supplies
  retained log lines when an event summary does not contain the failure cause.

Reads carry the person's `lake_token` and current `customer_id`, so lake applies the same policy as
it does for the person. Event cursors begin at one and continue from each returned
`next_sequence`; diagnostic reads use a zero wait when no live wait is needed.

## ApplicationAgent

Building a new App or changing an App's code or configuration is ApplicationAgent work. Ask Orama
delegates it to library key `agent-application`. The handler adds `kind: "app"` to `agent_turn`,
passes through known App or page context, and follows the returned task with
`receive_agent_events` just like every other library-agent task.

ApplicationAgent's initial turn is read-only. Its result is a proposal containing files and App
settings for the person to review. Ask Orama reports that proposal as proposed and does not claim
the App was created or changed. Lake starts a later confirmed turn with the reviewed proposal and
the write capabilities; Ask Orama never receives those App writes through delegation.

## Actions

Every App mutation remains a proposal. This includes `create_app`, `deploy_app`, `build_app`,
`rollback_app`, `scale_app`, start, stop, restart, deletion, environment, authentication and
binding changes. A direct operational request uses `lake_propose` with the exact capability and
input derived from the live index. The proposal is recorded in the answer and is never sent to the
capability endpoint by Ask Orama.

The fake-lake tests prove App and build reads, both retained event streams, the ApplicationAgent
turn kind and task follow, and that representative App actions create proposals without sending
writes. Fixed eval cases require `list_apps`; `get_app` plus `receive_app_events`; `list_builds`,
`get_build` plus `receive_build_events`; and delegation to `agent-application` with kind `app`.
