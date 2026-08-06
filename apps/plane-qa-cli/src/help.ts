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
  initiative list|create
  type list|create
  property list|create|set
  milestone list|create
  issue list|get|create|update|transition|comment|archive
      create|update also take --requirement-kind none|functional|quality
      (functional = the system must do this; quality = it must do it this well; none = not a requirement)
      list takes the same flag as a filter, comma-separated: --requirement-kind functional,quality
  folder list|get|create|update|delete
  case list|get|create|update|version|archive|link-issue|unlink-issue|attachments|attach|detach
      create|update also take --case-type functional|performance|security|reliability|compliance
      and a threshold: --threshold-metric --threshold-operator lt|lte|gt|gte --threshold-value --threshold-unit
      (metric, operator and value go together; unit is optional; changing any publishes a new version)
  search query --query 'type:test_case priority:high payment' [--scope all|test_cases|work_items]
  export testing --format csv|html|excel --output FILE [--query QUERY] [--scope SCOPE]
  run list|get|create|record-result|create-defect|close
  quality overview|coverage|release-gate|open-defects
  automation upload-junit|upload-results
  availability schedule|overlap|calendars|profiles|set-profile
      |leave-types|leaves|request-leave|cancel-leave|events
      schedule --from 2026-08-03 --to 2026-08-09 [--members ID,ID]
      overlap --members ID,ID --from DATE --to DATE [--duration 60]
      (returns 'core' — everyone said they may be interrupted — separately from 'working')
      set-profile --member ID [--calendar ID] [--timezone Asia/Taipei]
      [--start 09:00] [--end 18:00] [--core_start 14:00] [--core_end 17:00]
      [--hours 8] [--approver ID] [--clear_core_hours]
      leaves --from DATE --to DATE [--members ID,ID]
      request-leave --type ID --from DATE --to DATE
      [--start_part full|morning|afternoon] [--end_part ...] [--reason TEXT] [--member ID]
      (reasons are hidden from anyone but the member, their approver and admins)

All successful commands print JSON to stdout. Destructive commands require --yes or TTY confirmation.
Use --dry-run to preview destructive operations without writing.
`;
