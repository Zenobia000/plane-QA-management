# Testing management API

All endpoints use `X-API-Key`, project membership permissions, API throttling, and the prefix:

```text
/api/v1/workspaces/{workspace_slug}/projects/{project_uuid}/testing
```

| Resource     | Methods and paths                                                          |
| ------------ | -------------------------------------------------------------------------- |
| Discovery    | `GET /capabilities/`                                                       |
| Quality      | `GET /overview/`, `GET /requirement-coverage/`                             |
| Folders      | `GET,POST /folders/`; `GET,PATCH,DELETE /folders/{folder_uuid}/`           |
| Cases        | `GET,POST /test-cases/`; `GET,PATCH,DELETE /test-cases/{case_uuid}/`       |
| Versions     | `GET /test-cases/{case_uuid}/versions/{version}/`                          |
| Traceability | `GET,POST /test-cases/{case_uuid}/work-items/`; `DELETE .../{issue_uuid}/` |
| Runs         | `GET,POST /test-runs/`; `GET /test-runs/{run_uuid}/`; `POST .../close/`    |
| Results      | `POST /test-runs/{run_uuid}/cases/{run_case_uuid}/results/`                |
| Defects      | `POST .../results/{result_uuid}/defects/`                                  |
| Automation   | `POST /automation-ingestions/` with `Idempotency-Key`                      |

Test-case `PATCH` publishes a new immutable version. A created run pins each selected current version. Result writes append evidence; closing a run prevents further result mutation. Folder deletion succeeds only for an empty folder, and folder updates reject parent cycles.

List endpoints accept `per_page` where pagination is supported. Case lists additionally accept `search`, `folder_id`, and `work_item_id`.

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
