# Plane QA agent tooling runbook

## Build and verify

Requires the repository's Node and pnpm versions. From the repository root:

```bash
pnpm install
pnpm build:qa-tools
pnpm check:qa-tools
```

Set credentials in the process environment, never in tracked files:

```bash
export PLANE_URL="http://10.137.80.63:8787"
export PLANE_API_KEY="..."
export PLANE_WORKSPACE="workspace-slug"
export PLANE_PROJECT="PROJECT"
```

Rotate a token in Plane, replace `PLANE_API_KEY` in the secret manager or shell environment, restart local agent clients, and revoke the old token. Tokens are sent only as `X-API-Key`.

## CLI

```bash
node apps/plane-qa-cli/dist/cli.mjs project get
node apps/plane-qa-cli/dist/cli.mjs quality release-gate
node apps/plane-qa-cli/dist/cli.mjs case archive --case CASE_UUID --dry-run
node apps/plane-qa-cli/dist/cli.mjs search query --query 'type:test_case priority:high payment' --scope all
node apps/plane-qa-cli/dist/cli.mjs export testing --format excel --output testing.xlsx
node apps/plane-qa-cli/dist/cli.mjs case attach --case CASE_UUID --file evidence.png --mime-type image/png
```

Successful output is JSON on stdout. Errors are JSON on stderr. CI should use `--yes` only for reviewed destructive operations and a stable `--idempotency-key` for uploads.

## Codex

The tracked `.codex/config.toml` starts the built STDIO server and forwards only `PLANE_URL` and `PLANE_API_KEY`. Trust the project, export those variables before starting Codex, then restart Codex and inspect `/mcp`. Write tools use approval mode `writes`.

## Claude Code

The tracked `.mcp.json` references environment variables and contains no literal secrets; `.mcp.json.example` is the distribution template. Export the same variables, build the server, approve the project server in Claude Code, and inspect `claude mcp list`. Both clients use the same `plane-qa-mcp` process and tool schemas.

## Troubleshooting

- Server will not initialize: build `@plane/qa-mcp`, verify Node version and the repository working directory.
- Authentication: verify token rotation and `PLANE_URL`; never paste the token into an agent prompt.
- Permission: ensure the token owner is an active member of the target project.
- Not found: call project context and state tools; do not guess UUIDs.
- Conflict: re-read current state. For automation, reuse the same key only with the identical semantic payload.
- Timeout/rate limit: retry idempotent reads/uploads with backoff; do not blindly retry non-idempotent writes.
- API failure: retain the response `X-Request-ID` for server-log correlation.

Local STDIO is the supported deployment. Remote Streamable HTTP remains gated on HTTPS, per-user OAuth, scoped authorization, audit logging, token rotation, and operational rate limits.
