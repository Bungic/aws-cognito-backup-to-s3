# cognito-backup-to-s3

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![AWS Lambda](https://img.shields.io/badge/AWS%20Lambda-FF9900?logo=awslambda&logoColor=white)

A Lambda that backs up every Cognito user pool in your account (pool config, users, and groups) to a single S3 bucket. Designed to run on a daily schedule.

I wrote it because Cognito has no built-in backup. If someone deletes a pool, accidentally drops users, or you want a point-in-time snapshot for compliance, you need to roll your own. The full story is on Medium: [Automatically Backing Up AWS Cognito User Pools](https://furkangungor.medium.com/automatically-backing-up-aws-cognito-user-pools-8d62bfa4091a).

## How it works

On every invocation it lists the user pools in the configured region, then for each pool grabs `DescribeUserPool` (the full config: schema, MFA, password policy, triggers), `ListUsers` (everyone, with attributes and status), and `ListGroups` if any exist. The whole thing serialises to JSON and lands in S3 under `s3://<bucket>/<YYYY>/<MM>/<DD>/<pool_name>_<YYYYMMDD>.json`.

Per-pool error isolation: one failing pool does not abort the run. Returns `200` if every pool was backed up, `207` (multi-status) if at least one failed.

## Setup

| Variable | Required | Default | Notes |
|---|---|---|---|
| `BACKUP_BUCKET` | yes | (none) | Target S3 bucket. The Lambda refuses to start without it. |
| `AWS_REGION` | no | `eu-central-1` | Region where Cognito pools live |
| `BACKUP_TZ` | no | `Europe/Istanbul` | Timezone for the YYYY/MM/DD path prefix |

The bucket must exist before the Lambda runs. Versioning + a lifecycle policy (transition to Glacier after N days, delete after M days) is the recommended pairing, but those are outside this Lambda's scope.

## Deploy

```bash
zip function.zip cognito_backup_lambda.py
aws lambda update-function-code \
  --function-name cognito-backup-to-s3 \
  --zip-file fileb://function.zip
```

Recommended Lambda settings:
- Runtime: `python3.12`
- Handler: `cognito_backup_lambda.lambda_handler`
- Timeout: `300` seconds (more if you have many pools with tens of thousands of users)
- Memory: `512` MB (one pool's users are buffered in memory before upload)

### Schedule

Daily at 03:00 Europe/Istanbul via EventBridge Scheduler:

```bash
aws scheduler create-schedule \
  --name cognito-backup-daily \
  --schedule-expression "cron(0 3 * * ? *)" \
  --schedule-expression-timezone "Europe/Istanbul" \
  --flexible-time-window "Mode=OFF" \
  --target '{"Arn":"arn:aws:lambda:eu-central-1:<ACCOUNT_ID>:function:cognito-backup-to-s3","RoleArn":"arn:aws:iam::<ACCOUNT_ID>:role/cognito-backup-scheduler-role"}'
```

### IAM

See `iam-policy.json` for the Lambda execution role. Replace `<BACKUP_BUCKET>` with the actual bucket name in the policy before applying.

## What it doesn't do

No KMS encryption beyond S3 defaults. If your pool data is sensitive, enable SSE-KMS on the bucket and grant the Lambda role `kms:Encrypt`.

No password hashes. Cognito doesn't expose them. Backups capture every other user attribute and the status, but a fully deleted pool will need its users to reset passwords on the restored copy. Cognito limitation, not this script.

No cross-account or cross-region replication. The Lambda writes to one bucket. Use S3 CRR or AWS Backup for redundancy.

No restore tooling. The JSON has everything you need to recreate the pool, but the script that actually does the recreate isn't in this repo.

## Gotchas

The whole JSON for one pool sits in memory before upload (`Body=json.dumps(...)`). Hundreds of thousands of users in one pool can push Lambda memory usage uncomfortably high; raise the memory or shard the backup.

Pools with no groups raise `ResourceNotFoundException` on `list_groups`. The script swallows it and logs at INFO. Benign noise.

Same-day re-runs overwrite that day's file. If you need every run preserved, add the hour to the timestamp or enable S3 versioning on the bucket.

## Files

| File | What it is |
|---|---|
| `cognito_backup_lambda.py` | Lambda handler |
| `iam-policy.json` | Execution role policy |
| `requirements.txt` | Runtime deps (boto3, provided by Lambda runtime) |

## License

MIT, see [LICENSE](LICENSE).

---

Part of my cloud-engineering portfolio → **[frkangungor.com](https://frkangungor.com)**
