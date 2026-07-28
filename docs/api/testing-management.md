# Testing management API

All endpoints use `X-API-Key`, project membership permissions, API throttling, and the prefix:

```text
/api/v1/workspaces/{workspace_slug}/projects/{project_uuid}/testing
```

| Resource     | Methods and paths                                                                 |
| ------------ | --------------------------------------------------------------------------------- | ---------- | -------------------------- |
| Discovery    | `GET /capabilities/`                                                              |
| Quality      | `GET /overview/`, `GET /requirement-coverage/`                                    |
| Folders      | `GET,POST /folders/`; `GET,PATCH,DELETE /folders/{folder_uuid}/`                  |
| Cases        | `GET,POST /test-cases/`; `GET,PATCH,DELETE /test-cases/{case_uuid}/`              |
| Attachments  | `GET,POST /test-cases/{case_uuid}/attachments/`; `PATCH,DELETE .../{asset_uuid}/` |
| Versions     | `GET /test-cases/{case_uuid}/versions/{version}/`                                 |
| Traceability | `GET,POST /test-cases/{case_uuid}/work-items/`; `DELETE .../{issue_uuid}/`        |
| Search       | `GET /search/?query=...&scope=all                                                 | test_cases | work_items`                |
| Export       | `GET /export/?export_format=csv                                                   | html       | excel&query=...&scope=...` |
| Runs         | `GET,POST /test-runs/`; `GET /test-runs/{run_uuid}/`; `POST .../close/`           |
| Results      | `POST /test-runs/{run_uuid}/cases/{run_case_uuid}/results/`                       |
| Defects      | `POST .../results/{result_uuid}/defects/`                                         |
| Automation   | `POST /automation-ingestions/` with `Idempotency-Key`                             |

Test-case `PATCH` publishes a new immutable version. A created run pins each selected current version. Result writes append evidence; closing a run prevents further result mutation. Folder deletion succeeds only for an empty folder, and folder updates reject parent cycles.

List endpoints accept `per_page` where pagination is supported. Case lists additionally accept `search`, `folder_id`, and `work_item_id`.

Testing search spans current test-case versions and active Work Items in the same project. Free-text terms are combined with `AND`. The controlled query fields are `type`, `id`, `title`, `priority`, `status`, `tag`, and `folder`; for example:

```text
type:test_case priority:high tag:smoke "card payment"
type:work_item status:started checkout
```

This is a search DSL, not database SQL. Unknown fields are rejected and no arbitrary query reaches PostgreSQL. Export applies the same query and scope, returning UTF-8 CSV, standalone HTML, or a real XLSX workbook.

Attachment creation returns a presigned storage upload, followed by `PATCH` to confirm the upload. Lists include only confirmed, non-deleted files. Files are bound with `TESTING_ARTIFACT` and the test-case UUID, remain inside one workspace/project, and use the instance attachment MIME and size allowlists.

## Error contract

Public Testing errors use a stable envelope and repeat the request identifier in `X-Request-ID`:

```json
{
  "error": {
    "code": "http_409",
    "message": "Only an empty test folder can be deleted.",
    "details": { "error": "Only an empty test folder can be deleted." },
    "request_id": "e1eeeb33-9f67-4f69-94a6-8a2a0d062feb"
  }
}
```

Clients may send `X-Request-ID`; otherwise the API generates one. Do not log or return API tokens.

## Minimal lifecycle

1. Create a case with `title`, optional `folder_id`, and structured `steps`.
2. Link it using `{ "issue_id": "..." }`.
3. Create a run using `{ "name": "Smoke", "test_case_ids": ["..."] }`.
4. Append a result using `{ "status": "failed", "actual_result": { "text": "HTTP 500" } }`.
5. Create a defect from that result, append a later retest, then explicitly close the run.

Automation payloads and idempotency semantics are documented in [testing-automation.md](testing-automation.md).
