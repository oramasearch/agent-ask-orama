# The Quickstart's model step

Lake's Quickstart (lake#1182, lake `docs/api/quickstart.md#the-conversation-lake1182`) opens an Ask
Orama conversation once a dropped dataset's search works. Lake sends every turn of it with a `page`
that names the dataset, so Ask Orama answers "what could I build with this?" without asking which
dataset.

## What Lake sends

`page` (text values): `path` (`/`), `quickstart`, `quickstart_id`, `dataset`, `dataset_id`,
`dataset_path` (`<database>.<table>`, for SQL), `rows`, `columns` (each with its detected kind and
"(can be predicted)"), `predictable_columns` (or `none: …`), `search_index`,
`search_index_published` and `snapshot_date`; and where the Quickstart is (lake#1204):
`quickstart_state` (`deciding`, `training`, `failed`, `trained` or `done`), `model` (what was asked
for, training or trained), `model_problem` (why it failed, in plain words) and `quickstart_next`
(the person's next step). Lake works the page out again on every status read, so each reply carries
the current state. Lake also writes the outcome of a confirmed `train_quickstart` into the
conversation (what started and what comes next, or why it failed), never "Done: train_quickstart".

## What Ask Orama does with it

`quickstart_text` in `agent.py` appends a direction to the turn whenever `page.quickstart_id` is
set, and prompt v16's (and v17's) *What to build with a dataset* section says how to answer:

- the dataset is known: never ask which one, never look for "the last uploaded";
- ideas first, the most interesting first, each tied to its columns: a yes-or-no model
  (`train_quickstart` with `target`), a derived target (`train_quickstart` with `derived_target`:
  a threshold or band on a number column read from the data, or values that count as yes),
  clustering (`train_quickstart` with `methodology: "M-3"`, after this turn's `list_methodologies`
  read; its model is not added to the website), Auto-Suggest opportunities (`agent-autosuggest`),
  an analysis from reads, an app such as an analysis dashboard (`agent-application`, kind app);
- the strongest model is proposed at once as `train_quickstart`, so one Confirm starts it;
- a bundle (a clustering model, a dashboard app over its segments, opportunities) is several
  proposals and delegations the person confirms one by one;
- a generated corpus or labels (`generate_dataset`, cost first) only when nothing else fits or the
  person asks; "what could I build?" never goes to `agent-autosuggest-corpus` or
  `agent-project-corpus`, which train Orama's own agents;
- a model in the Quickstart is always `train_quickstart`, never `compile_intent` or a new project.

## After a confirm (prompt v17)

`quickstart_text` gives each state its own direction, and prompt v17's *Following the Quickstart
after a confirm* says how to answer:

- `training`: say what started and what comes next; asked about progress ("is it finished?"), read
  `quickstart_status` with the page's `quickstart_id` in this turn and answer from it;
- `failed`: say why in the person's words (`model_problem`), then propose the corrected change as a
  `train_quickstart` card (another column that names a row or none, another target or derived
  target, M-1 when clustering cannot work), and point at the page's **Try again** when a retry can
  fix it;
- `trained` or `done`: say what they can do now (`quickstart_next`);
- never tell the person to "configure" anything internal: graph hints, a K range, a holdout, engine
  settings or capability names. On 2026-10-25 a failed clustering was answered with "configure the
  segmentation K range", which a person can't do (lake#1203, lake#1204).

Ask Orama still never writes: every one of these is a proposal Lake shows as the exact call and runs
only when the person confirms it (`confirm_ask_proposal`).

## Verify

`uv run pytest`: `test_a_quickstart_turn_names_the_dataset_and_never_asks_which_one`,
`test_the_prompt_leads_a_quickstart_with_ideas_not_a_corpus` and
`test_a_quickstart_clustering_proposal_runs_train_quickstart_after_the_registry_read`;
for v17, `test_a_quickstart_turn_follows_the_training_and_the_failure`,
`test_the_prompt_follows_the_quickstart_after_a_confirm` and
`test_after_a_failure_it_reads_the_status_and_proposes_the_corrected_change`.
