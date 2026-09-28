# Tests

`test_agent.py` uses an `httpx` fake lake and a scripted model client. Its methodology coverage
includes a runnable M-3 proposal, an M-14 proposal declined with `zetta#1053`, the M-1-only fallback
for an older engine, and deterministic grading of the segmentation and speech eval cases.

`test_lake_bus.py` covers task receipt and result publication on lake's agent bus.

Run all tests with `uv run pytest`.
