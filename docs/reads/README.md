# Reads: what one read hands the model

Every `lake_read`, `compare_models`, `mcp_tool` read and delegated answer reaches the model as one
observation (`observation` and `fit` in `agent.py`): the capability's JSON value, at most
`OBSERVATION_LIMIT` (20000) characters.

## A long list is trimmed by its items, never cut mid-text

Until agent-ask-orama#21 an observation was the JSON text sliced at 20000 characters. The engine's
`list_datasets` answers every dataset with its full schema and no total, so on the dev Lake
"How many datasets are in this workspace?" got a list cut off mid-item and the answer "at least
25 ... the tool output was cut off mid-result". A count is a basic question the answer must get
right.

Now a value that fits goes as it is. One that does not is trimmed by the items of its lists (each
top-level list of an object, or a top-level list as `items`):

1. every item reduced to its own scalar fields (nested objects and lists dropped, strings over
   200 characters shortened), when all of them fit;
2. otherwise, as many of those compact items as fit, from the first.

The trimmed observation carries `_observation`:

```json
{"datasets": [{"name": "dataset_001", "rows": 1001}],
 "_observation": {"lists": {"datasets": {"count": 63, "shown": 63, "detail": "scalar fields only"}},
                  "note": "datasets: 63 items in this answer, all shown. ... These counts were taken before trimming: use them, not a count of the items shown."}}
```

`count` is the list's length taken before trimming, `shown` how many items the observation keeps.
When the capability gives its own `total` (and the value has one list), it is there as `total`.
The note tells the model to read one item by its id for the detail trimming dropped.

## A paged answer says more follow

An answer with a `next_cursor`, `has_more: true` or `done: false` (lake's paged reads, such as
`list_transcripts`, `list_secrets`, `list_artifacts`) is annotated even when it fits: the note says
the page is not all of the items, gives the capability's `total` when there is one (otherwise the
total is unknown until the last page) and the `cursor` to pass for the next page. Ask Orama does
not read every page on its own: the model reads the next page when the question needs it.

## The last resort

A value too long with no list to trim (one huge field) is cut, and the cut is said:
`[OBSERVATION CUT at 20000 of N characters: the JSON above is incomplete; its lists held ... items
before cutting. Do not count what is shown.]`. It is never silent.

## Verification

`tests/test_agent.py` reads a fake `list_datasets` of 63 datasets with full schemas (longer than one
observation) and checks the model sees whole JSON within the limit with `count` 63; a list too
long even compact keeps as many items as fit and says how many; a short answer goes unchanged; a
paged answer gives the capability's total and the next cursor; a value with no list is cut with the
note. The eval runner's `count` cases ask "How many datasets / trained models / runs are in this
workspace?" and grade the reply against the exact number the runner read from the same lake before
the turn, failing a hedge such as "at least" or "cut off".
