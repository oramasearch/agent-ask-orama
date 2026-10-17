# Models and Unfinished Turns

What Ask Orama does when a person asks which of their models is best, and what happens when a turn
runs out of tool rounds ([agent-ask-orama#14](https://github.com/oramasearch/agent-ask-orama/issues/14)).

## Which Model Scored Best

The lake UX review of 2026-10-10 asked *"Which of my models in project … scored best on held-out
AUC?"*. Ask Orama spent all ten tool rounds on `list_runs` (with a `limit` over the engine's 20),
`get_model` with the wrong input, and other reads, and never reached a held-out score. The engine's
run metrics carry no held-out score ([zetta#1239](https://github.com/oramasearch/zetta/issues/1239)),
so the only reads that hold one are `get_run_report` (one call per run) and `list_models`, whose
`metrics` keep the `held_out_*` figures training wrote on each model.

`compare_models` is Ask Orama's tool for this question. One call:

1. reads lake's named `list_models` as the person (lake#650), or
   `workspace_query {"capability": "list_models", "input": {}}` on an older lake;
2. keeps the models of the project the person named (by name or id, ignoring case), or every
   model when none is named;
3. ranks them by one held-out figure: `held_out_auc` when the models have it, then
   `held_out_accuracy`, `held_out_rmse`, `held_out_log_loss`, else the most common held-out
   figure. Loss and error figures rank lower-is-better, the rest higher-is-better;
4. answers `{project, count, ranked_by, direction, best, models}`, best first. A model without
   held-out figures comes last with its in-sample figures and a note that its run held no rows
   out, so it is never ranked against held-out scores.

The read is recorded in the turn's `reads` as `list_models` (or `workspace_query` /
`list_models`). Prompt `v10` sends
"which model is best" and "how do these runs compare" to `compare_models` first, keeps
`get_run_report` for detail about one run, and states the inputs of the run and model reads
(`list_runs` `limit` at most 20; `get_model {"id"}`; `get_run_report {"run_id"}`). Finding a
*new* best model (a training study) still goes to Experiments Agent.

## A Turn That Runs Out of Rounds

A turn has `MAX_ROUNDS` (10) tool rounds. Before, the last round ended with *"I stopped before
finishing: this turn reached its limit of tool rounds."*, returned as an ordinary answer, so lake
recorded the task as `succeeded`.

Now, when the rounds run out:

- Ask Orama makes one more model call with `tool_choice: "none"` and an instruction to answer
  without tools: start with *"I did not finish this."*, say what it found (quoting only tool
  results) and what is still unknown. If that call fails or answers nothing, the reply is a fixed
  sentence that says the turn did not finish.
- The answer carries `incomplete: true`.
- `run_turn` answers `{ok: false, incomplete: true, error: <the partial answer>, …}`. On lake's
  agent bus, `lake_bus.run_task` publishes it as `failed` with the partial answer as its message,
  so `get_agent_task` reports `failed`, never `succeeded`. Lake shows it in the conversation as
  *"That did not finish: I did not finish this. …"*. `POST /v1/turn` answers it with HTTP 422.

A distinct `incomplete` task status in lake would need a new phase in lake's agent bus and its
dispatch schema; `failed` with an honest message is what lake shows today.

## How to Verify

- `uv run pytest`: `test_which_model_scored_best_is_one_read_of_every_models_held_out_scores`,
  `test_compare_models_names_an_empty_project_and_a_failed_read`,
  `test_a_turn_out_of_rounds_ends_unfinished_with_an_honest_partial_answer`,
  `test_an_empty_or_failed_partial_answer_still_says_it_did_not_finish`,
  `test_the_model_score_eval_needs_list_models_held_out_scores_and_a_finished_turn`, and in
  `test_lake_bus.py`, `test_an_unfinished_turn_is_published_as_failed_with_its_partial_answer`.
- Live: the `model-scores` eval case (`ask-orama-evals`) asks the question against a real lake and
  fails if `list_models` was not read, the reply has no held-out score, or the turn ran out of
  rounds. Every eval case now fails when its turn ran out of rounds.
