# The Quickstart's model step

Lake's Quickstart (lake#1182, lake `docs/api/quickstart.md#the-conversation-lake1182`) opens an Ask
Orama conversation once a dropped dataset's search works. Lake sends every turn of it with a `page`
that names the dataset, so Ask Orama answers "what could I build with this?" without asking which
dataset.

## What Lake sends

`page` (text values): `path` (`/`), `quickstart`, `quickstart_id`, `dataset`, `dataset_id`,
`dataset_path` (`<database>.<table>`, for SQL), `rows`, `columns` (each with its detected kind and
"(can be predicted)"), `predictable_columns` (or `none: …`), `search_index`,
`search_index_published` and `snapshot_date`.

## What Ask Orama does with it

`quickstart_text` in `agent.py` appends a direction to the turn whenever `page.quickstart_id` is
set, and prompt v16's *What to build with a dataset* section says how to answer:

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

Ask Orama still never writes: every one of these is a proposal Lake shows as the exact call and runs
only when the person confirms it (`confirm_ask_proposal`).

## Verify

`uv run pytest`: `test_a_quickstart_turn_names_the_dataset_and_never_asks_which_one`,
`test_the_prompt_leads_a_quickstart_with_ideas_not_a_corpus` and
`test_a_quickstart_clustering_proposal_runs_train_quickstart_after_the_registry_read`.
