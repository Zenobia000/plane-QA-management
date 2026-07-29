# AI software-delivery demo

`seed_ai_software_demo` creates a connected Plane project for demonstrating product management,
JIRA-style work items, AI-assisted software development, and QA evidence in one project scope.

## Create the demo

Run the command inside the API environment against an existing workspace:

```bash
python manage.py seed_ai_software_demo --workspace <workspace-slug>
```

The default project identifier is `AIDEMO`. To replace a previously generated demo:

```bash
python manage.py seed_ai_software_demo --workspace <workspace-slug> --force
```

Object storage is optional. If MinIO/S3 is unavailable, use `--skip-attachments`; all other project
data is still created. Do not use `--force` on a project containing hand-written data.

## What is created

- Initiative: `AI-native software delivery foundation`
- Project: `AI DevFlow Copilot Demo`
- Work-item types: Epic, Feature, Story, Task, Bug
- Planning: 2 milestones, 4 modules, 3 cycles
- Delivery graph: 2 epics, 4 features, 10 stories, 6 tasks, a known bug, and a defect created from QA
- Work-item context: parents, assignee, cycle/module/milestone membership, relations, link, and comment
- Testing: 7 folders, 11 linked versioned cases, one closed manual run, one CI ingestion, and one active run
- Evidence: Markdown actual results, retry/retest history, result and case attachments, defect traceability,
  and 5 release-evidence records

The active release run intentionally contains blockers. This makes the quality overview useful for
demonstrating failed, blocked, passed, open-defect, missing-contract, and pending-sign-off states.

## Custom fields

The seed covers every supported property kind.

| Field             | Kind         | Example                                            |
| ----------------- | ------------ | -------------------------------------------------- |
| Requirement kind  | select       | `functional`, `non_functional`                     |
| AI capabilities   | multi-select | `llm`, `rag`, `agents`, `evaluation`, `guardrails` |
| Delivery note     | text         | Acceptance and scope note                          |
| Story points      | number       | `8`                                                |
| Target release    | date         | Relative to the seed date                          |
| AI assisted       | boolean      | `true`                                             |
| Risk level        | select       | `low`, `medium`, `high`, `critical`                |
| Specification URL | URL          | Canonical demo specification                       |

## Labels

- Areas: `area:product`, `area:frontend`, `area:backend`, `area:ai`, `area:platform`
- Roles: `role:pm`, `role:qa`
- Quality: `quality:security`, `quality:privacy`, `quality:performance`, `quality:accessibility`
- Execution: `automation`, `manual`, `release-blocker`

## Useful searches

```text
type:test_case tag:security
type:test_case tag:attachment markdown
priority:high AI
AIDEMO-1
```

The same result set can be exported from Testing as CSV, HTML, or Excel.
