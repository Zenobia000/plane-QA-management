# PostgreSQL and MinIO backup/restore drill — 2026-07-14

Scope: WBS 7.3 against the disposable localhost Testing stack created during the source-image smoke.

## Procedure and evidence

1. Created PostgreSQL table `ops_restore_drill` with marker value `before-backup`.
2. Created MinIO-volume object `/export/restore-drill/marker.txt` with value `before-backup`.
3. Ran `deployments/testing-localhost/backup.sh`; PostgreSQL dump, MinIO archive, source commit, resolved Compose, and
   `SHA256SUMS` were produced.
4. Verified every checksum successfully.
5. Changed both markers to `after-backup` and queried/read them to prove the post-backup mutation existed.
6. Ran the guarded destructive restore with `CONFIRM_RESTORE=ERASE_AND_RESTORE_PLANE`.
7. Restore checksum verification passed, PostgreSQL schema/data reloaded, MinIO volume reloaded, and the migrator
   reported no pending migrations.
8. Queried PostgreSQL and read MinIO after restore; both independently returned `before-backup`.
9. Caddy returned HTTP 200 and the Web container reached the API over the Compose network.
10. API, Web, worker, and beat-worker were verified on source tag `d3d3de44c` after restore.

## Finding and correction

The first restore recreated application services with the default `:dev` tag because the script did not restore the
source-image tag. `restore.sh` now computes Git's unique short hash from the backed-up full commit unless
`PLANE_TESTING_TAG` is explicitly supplied. A fixed character count was rejected because Git abbreviation length is
repository-dependent.

## Result

PASS. The drill proves both persistent stores can be recovered together and the source-built service identity is
restored. It does not yet prove an upgrade from a pre-change sanitized dataset; that remains WBS 7.4.
