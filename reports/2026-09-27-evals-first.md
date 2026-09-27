# Ask Orama evals, 2026-09-27

**10 / 22 passed** with `gpt-5.5` against `https://lake.oramadev.net`.
Generated from lake's live capability index; graded by rules (evals.py), no judge.

| Case | Kind | Expected | Result |
|---|---|---|---|
| `change-revoke_device` | change | `revoke_device` | FAIL: did not propose revoke_device |
| `change-delete_application_user` | change | `delete_application_user` | FAIL: did not propose delete_application_user |
| `change-scim_list_users` | change | `scim_list_users` | pass |
| `change-create_domain` | change | `create_domain` | FAIL: did not propose create_domain |
| `change-create_invitation` | change | `create_invitation` | FAIL: did not propose create_invitation |
| `change-workspace_act` | change | `workspace_act` | FAIL: did not propose workspace_act |
| `change-create_pipeline` | change | `create_pipeline` | pass |
| `change-rotate_tuf_root` | change | `rotate_tuf_root` | pass |
| `change-create_drive_share_link` | change | `create_drive_share_link` | FAIL: did not propose create_drive_share_link |
| `change-update_issue` | change | `update_issue` | FAIL: did not propose update_issue |
| `read-get_secret_mount` | read | `get_secret_mount` | FAIL: did not read get_secret_mount |
| `read-get_change` | read | `get_change` | FAIL: did not read get_change |
| `read-get_encryption_key` | read | `get_encryption_key` | FAIL: did not read get_encryption_key |
| `read-list_conflicts` | read | `list_conflicts` | pass |
| `read-list_changes` | read | `list_changes` | pass |
| `read-get_dataset` | read | `get_dataset` | FAIL: did not read get_dataset |
| `read-get_user` | read | `get_user` | FAIL: did not read get_user |
| `read-list_users` | read | `list_users` | pass |
| `delegate-agent-project-0` | delegate | `agent-project` | pass |
| `delegate-agent-project-1` | delegate | `agent-project` | pass |
| `delegate-agent-autosuggest-2` | delegate | `agent-autosuggest` | pass |
| `delegate-agent-autosuggest-3` | delegate | `agent-autosuggest` | pass |
