# Plane QA tool reference

All MCP tools require a workspace slug. Project-scoped tools accept a project UUID or identifier. Read tools are approval-safe; writes may require agent approval; destructive tools additionally require `confirm: true`.

| Domain     | MCP tools                                                                                                                                                                 | CLI group        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Context    | `project_list`, `project_get_context`, `project_state_list`                                                                                                               | `project`        |
| Project    | `project_update`                                                                                                                                                          | `project update` |
| Work items | `issue_list`, `issue_get`, `issue_create`, `issue_update`, `issue_transition`, `issue_add_comment`, `issue_archive`                                                       | `issue`          |
| Folders    | `test_folder_list`, `test_folder_get`, `test_folder_create`, `test_folder_update`, `test_folder_delete`                                                                   | `folder`         |
| Cases      | `test_case_list`, `test_case_get`, `test_case_create`, `test_case_update`, `test_case_version_get`, `test_case_link_issue`, `test_case_unlink_issue`, `test_case_archive` | `case`           |
| Runs       | `test_run_list`, `test_run_get`, `test_run_create`, `test_result_record`, `test_result_create_defect`, `test_run_close`                                                   | `run`            |
| Quality    | `quality_overview`, `quality_requirement_coverage`, `quality_release_gate`                                                                                                | `quality`        |
| Automation | `automation_upload_junit`, `automation_upload_results`                                                                                                                    | `automation`     |

CLI success is JSON on stdout. Errors are JSON on stderr with stable exit codes: `1` validation, `2` usage, `3` authentication, `4` permission, `5` not found, `6` conflict, `7` confirmation refusal, `8` network/rate-limit/server. Destructive CLI operations accept `--yes`, interactive `yes`, or `--dry-run`.

Use `PLANE_URL`, `PLANE_API_KEY`, `PLANE_WORKSPACE`, and optional `PLANE_PROJECT`. Never pass the token in prompts or commit it in configuration.
