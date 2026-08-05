# AI software-delivery demo

`seed_ai_software_demo` creates a connected Plane project for demonstrating product management,
JIRA-style work items, AI-assisted software development, and QA evidence in one project scope.

This is the second of two demo seeds, and the one to reach for when the subject is custom-field
kinds or evidence attachments. It predates `plane/testing/demo/` and still carries the default
five-state board, so anything about the delivery process, workflow states, coverage rules or the
Project Overview belongs to `seed_testing_demo` instead. Both are compared, with `--force`
semantics and the repair commands, in
[`.agents/skills/plane-qa/references/demo-data.md`](../../.agents/skills/plane-qa/references/demo-data.md).

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
| AI capabilities   | multi-select | `llm`, `rag`, `agents`, `evaluation`, `guardrails` |
| Delivery note     | text         | Acceptance and scope note                          |
| Story points      | number       | `8`                                                |
| Target release    | date         | Relative to the seed date                          |
| AI assisted       | boolean      | `true`                                             |
| Risk level        | select       | `low`, `medium`, `high`, `critical`                |
| Specification URL | URL          | Canonical demo specification                       |

**Requirement kind is deliberately absent from that table.** It was seeded here as a custom
`select` property and is now `Issue.requirement_kind`, a first-class field carrying
`functional` / `quality` / `none`. A custom property is defined per project, so every new
project had to declare it before "which of these are quality requirements" could be asked at
all, and a report spanning projects could never ask it. Seeding it as a property _as well_
would leave the demo teaching a pattern the model no longer uses, and give the same question
two places to disagree. See `docs/process/plane-qa-guideline.md` B2.

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
