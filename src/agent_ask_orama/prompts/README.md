# Prompts

Each prompt behavior change creates a new version; previous versions remain for trace history.
`agent.py` selects the active version through `PROMPT_VERSION`.

- `v5.md` reads the live methodology registry, declines unsupported Pipeline work with its issue,
  explains graph `methodology` / `runnable` fields, and uses the M-1-only older-engine fallback.
- `v4.md` knows the three corpus generators it can bring into a turn.
- `v3.md` maps project identifiers to names and identifies deleted projects.
- `v2.md` documents workspace data reads and the supported SQL subset.
- `v1.md` defines Ask Orama's base read, propose and delegate behavior.
