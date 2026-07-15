export const HELP_TEXT = `plane-qa — integrated Plane project and QA management

Usage:
  plane-qa <group> <action> [options]

Configuration:
  --url URL                 or PLANE_URL
  --api-key TOKEN           or PLANE_API_KEY
  --workspace SLUG          or PLANE_WORKSPACE
  --project ID|IDENTIFIER   or PLANE_PROJECT

Commands:
  project list|get|update|states
  issue list|get|create|update|transition|comment|archive
  folder list|get|create|update|delete
  case list|get|create|update|version|archive|link-issue|unlink-issue
  run list|get|create|record-result|create-defect|close
  quality overview|coverage|release-gate|open-defects
  automation upload-junit|upload-results

All successful commands print JSON to stdout. Destructive commands require --yes or TTY confirmation.
Use --dry-run to preview destructive operations without writing.
`;
