# Releases

One page per tagged release, newest first. A page states what the release includes, what it does
not include, known issues, verification output, and where the image runs. The first release lists
everything: every tool, turn kind, route, entry point and environment variable.

A release has one `vX.Y.Z` name shared by the Git tag, the GitHub release and the Docker Hub
image tag `oramasearch/agent-ask-orama:vX.Y.Z`. The image tag names the digest already built and
verified; it is never produced by a second build.

| Release | Date | Summary |
|---|---|---|
| [v0.2.1](v0.2.1.md) | 2026-10-25 | A patch: prompt v17 follows the Quickstart after a confirm (what started, progress from `quickstart_status`, the corrected proposal after a failure; lake#1204) |
| [v0.2.0](v0.2.0.md) | 2026-10-25 | A minor: the security-review fixes (constant-time service token refused when unset, the credential only to `LAKE_URL`, conversations owned by Lake's claim and bounded, bus backpressure, no trace file), prompt v15 (only proposals that can work) and v16 (the Quickstart's model step) |
| [v0.1.1](v0.1.1.md) | 2026-10-19 | A patch: prompt v14 answers how-to questions from Lake's Docs, with the exact page names and links, and a `how_to` eval case |
| [v0.1.0](v0.1.0.md) | 2026-10-17 | The first release: the Ask Orama turn on prompt v13 (read as the person, propose every change, delegate through Lake), the `methodology_draft` turn, the HTTP API, the agent bus worker and the image |

`pyproject.toml`'s `[project].version` is the one place the version is set; `GET /healthz` reports
it, and `tests/test_release.py` fails when that version has no page here.
