# Testing automation API

Endpoint:

```text
POST /api/v1/workspaces/{workspace_slug}/projects/{project_id}/testing/automation-ingestions/
X-API-Key: <Plane API token>
Idempotency-Key: <stable CI run attempt key>
Content-Type: application/json
```

JUnit request:

```json
{
  "format": "junit",
  "source": "github-actions",
  "name": "main / test / 421",
  "build": "git-sha",
  "configuration": { "os": "ubuntu", "python": "3.13" },
  "artifact_ids": ["a pre-uploaded Plane FileAsset UUID"],
  "junit_xml": "<testsuite>...</testsuite>"
}
```

Generic request:

```json
{
  "format": "results",
  "source": "playwright",
  "name": "browser regression",
  "results": [
    {
      "external_id": "checkout/card/visa",
      "title": "Visa checkout",
      "status": "passed",
      "duration_ms": 812,
      "actual_result": {}
    }
  ]
}
```

Allowed statuses are `passed`, `failed`, `blocked`, and `skipped`. The first successful request returns 201. An identical
retry returns 200 with `replayed: true`; the same key with changed semantic content returns 409. `diagnostics` identifies
auto-created mappings, invalid rows, and duplicate identities. Use a key stable for one logical CI upload, such as
`{repository}:{workflow_run_id}:{job}:{attempt}`.
