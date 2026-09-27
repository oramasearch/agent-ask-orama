Dated eval reports from `ask-orama-evals`, run against a real lake.

- `2026-09-27-evals-first.*`: the first live run, 10/22. It found a real bug (a `customer_id` added to
  reads that take none, so `identity` always failed) and an unfair generator (asks for "get user"
  with no user named, graded as failures when Ask Orama rightly asked which one).
- `2026-09-27-evals.*`: after both fixes, 22/24. The two failures are left as produced: `create_user`
  (it asked for the new user's email rather than inventing one) and `timestamp_checkpoint` (it found
  no published checkpoint to timestamp and said so).
