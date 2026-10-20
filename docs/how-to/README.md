# How-to questions: answered from Lake's Docs

A question about using Lake itself ("How do I load my first dataset?", "Where do I add a
connection?") is answered from **Lake's Docs**, read in the turn, never from what data products
usually look like (prompt `v14`, [lake#817](https://github.com/oramasearch/lake/issues/817)).

## Why

"How do I load my first dataset?" is the first suggestion on Lake's home, so it is likely the
first answer a new person reads. On lake-dev (2026-10-18) prompt `v13` answered it with:

> 1. Go to **Lake Console → datasets / data upload** in your workspace.
> 2. Choose **Upload dataset**.
> 3. Pick a file, usually CSV or Parquet.

No page is called "Lake Console", there is no "Upload dataset" button, the upload refuses Parquet,
and nothing was linked. The real path is **Data → Datasets → Load data → Upload**, for a CSV or
JSONL file, with **Generate**, **From a connection** and a drive's **Load as dataset** as the
other ways in.

## What the prompt says

`prompts/v14.md`, *Questions about using Lake: answer from the Docs*:

- read `list_docs` with the subject's key words, then `get_doc` for the best guide, and answer from
  it; with no guide, say so;
- name pages, tabs and buttons exactly as the guide and the navigation show them, as a path joined
  by arrows, never inventing or renaming one ("Lake Console" is the product, not a page);
- link each page with the link the guide gives (`[Data → Datasets → Load data](/train/data)`) and
  the guide itself (`/docs/<slug>`);
- name only the formats, sizes and limits the guide states.

Both reads are public lake capabilities, in the index every turn derives from lake's OpenAPI. Lake
keeps the guides right for this reader: each page a guide sends a person to is written as the rail
shows it and linked to its path, and lake's
`AskOramaGuidance.TheDocsAnswerTheHomesFirstSuggestionWithTheRealPath` test holds the Datasets
guide to the rail and to the formats `upload_dataset` accepts.

## The eval

`evals.py` generates a `how_to` case for each of `HOW_TO_QUESTIONS`, asked from the home
(`page.path` `/`). It passes when the turn read `list_docs` or `get_doc`, the reply names the path
(`data → datasets → load data`, any arrow) and links `/train/data`, and it names none of
`REFUSED_FORMATS` (Parquet, Excel, Avro, …) as one to load and no "Lake Console" page. A sentence
that names a refused format only to turn the person away from it ("Parquet is not accepted: save it
as CSV first", as the guide itself says) is not counted.
`test_the_how_to_eval_holds_the_answer_to_the_homes_first_suggestion` grades the recorded lake-dev
answer as failing on each of those and a Docs-based answer as passing. The live runner has not yet
run this case.
