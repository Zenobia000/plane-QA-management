# Current localhost copy upgrade migration rehearsal — 2026-07-14

Scope: WBS 7.4, upgrading a sanitized copy of the current localhost PostgreSQL data from the pre-Testing migration head
`db.0121` to the current Testing head `db.0125` without touching the live volume during migration execution.

## Isolation and source

- Created a dedicated Docker network with temporary PostgreSQL 15.7 and Valkey 7.2 containers and no host ports.
- Added an invalid-domain rehearsal user, workspace, membership, and project (`localhost-upgrade-copy/LUC`) to the
  disposable localhost stack, dumped the current database, then removed those rows after the drill.
- Current-copy dump SHA-256:
  `5afd546b67956c9c6f488839f84f95f61e8de97b8b51e159b99e7fb00e10eb6e`.
- Restored that dump only into the isolated PostgreSQL container.

## Pre-upgrade state

1. Used Django's reversible migration graph to move the restored current copy from `db.0125` to `db.0121`.
2. Reverse migrations 0125, 0124, 0123, and 0122 all completed with `OK`.
3. The sanitized project still queried as `localhost-upgrade-copy/LUC`.
4. The correct database query reported zero `test_%` tables.
5. The pre-Testing copy at 0121 was dumped with SHA-256
   `2f8a117296dad2e5804ca3bbeb331c35e7dca67a47cb434f1fb32ad1c273167e`.

## Upgrade and acceptance

1. Ran the current source API image (`plane-testing-api:d3d3de44c`) against the isolated 0121 database.
2. Forward migrations `0122_testing_library`, `0123_testing_runs`, `0124_testing_defects`, and
   `0125_testing_automation` all completed with `OK`.
3. The original invalid-domain user, workspace, and project were retrieved through current Django models after upgrade.
4. Eleven `test_%` tables existed after upgrade (zero before upgrade).
5. `create_test_case` created the first case for the preserved project with project sequence 1.
6. `makemigrations --check --dry-run` reported `No changes detected`.
7. Temporary containers/network and sanitized rehearsal rows were removed; the localhost proxy continued returning
   HTTP 200.

## Result

PASS. This proves a copy of current localhost Plane data can cross the pre-Testing → Testing schema boundary while
preserving existing domain rows and accepting writes through the new Testing application service.
