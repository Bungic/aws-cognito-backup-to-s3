# Changelog

## [0.1.0] - 2026-05-20

Initial public release.

- Daily backup of every Cognito user pool in the configured region to a single S3 bucket.
- Captures pool config (`DescribeUserPool`), users (`ListUsers`), and groups (`ListGroups`).
- Per-pool error isolation: one failing pool does not abort the run.
- HTTP-style return code: `200` on full success, `207` when at least one pool failed.
- Timezone-aware date path prefix (default `Europe/Istanbul`).
- `BACKUP_BUCKET` is a required environment variable; without it the Lambda won't load.
