# Upstream merge rehearsal for the Plane Testing fork

1. Create and verify a localhost backup using `deployments/testing-localhost/backup.sh`.
2. Record `git status --short`, the current fork commit, and upstream target commit in the rehearsal log.
3. Fetch upstream and create `rehearsal/upstream-YYYYMMDD` from the fork branch.
4. Merge the pinned upstream target without deleting local changes. Resolve by extension seam:
   Testing models/migrations, App/Public URLs, root MobX store, project sidebar, then package exports.
5. Run Python compilation, Django migration checks and Testing contract suites.
6. Run package type checks and `pnpm turbo run build --filter=web`.
7. Run `deployments/testing-localhost/rehearse-upgrade.sh` against a restored/sanitized copy—not the sole live copy.
8. Execute Library, fixed run, defect/retest, release gate, CSV, JUnit retry and artifact acceptance journeys.
9. Store conflicts, decisions, commands and results in `docs/operations/rehearsals/YYYY-MM-DD-upstream.md`.

Minimum affected Django suite:

```bash
pytest plane/tests/unit/testing plane/tests/unit/models/test_testing_library.py \
  plane/tests/contract/app/test_testing_*.py plane/tests/contract/api/test_testing_automation.py
```

A rehearsal is not successful when only merge conflicts are resolved; migrations, restored data and runtime journeys are
part of the gate.
