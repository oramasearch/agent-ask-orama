# Tests

`test_agent.py` uses an `httpx` fake lake and a scripted model client. Its methodology coverage
includes a runnable M-3 proposal, an M-14 proposal declined with `zetta#1053`, the M-1-only fallback
for an older engine, and deterministic grading of the segmentation and speech eval cases. Its
solution coverage includes a runnable entry, a preview with missing production components, a
refused sketch, an older engine, policy and evidence reads, an unavailable operation, a policy
proposal that is never sent, and deterministic solution eval grading. Its App coverage includes
lists, current health with retained events, build-failure diagnosis, ApplicationAgent delegation
with kind `app`, proposal-only actions and deterministic App eval grading.
Its experiment coverage routes train, tune and best-model requests to `experiment`, progress to
`experiment_status`, and divergence questions to `experiment_explain`; it also proves Ask Orama
cannot forward confirmed proposal or promotion objects and grades the fixed experiment evals.

`test_lake_bus.py` covers task receipt and result publication on lake's agent bus.

Run all tests with `uv run pytest`.
