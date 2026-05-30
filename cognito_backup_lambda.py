"""Backup every Cognito user pool (config + users + groups) to S3 daily.

S3 key layout: <bucket>/<YYYY>/<MM>/<DD>/<pool_name>_<YYYYMMDD>.json
Timezone for the date path: Europe/Istanbul.
"""

import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "eu-central-1")
BACKUP_BUCKET = os.environ["BACKUP_BUCKET"]  # required, no default
TZ = ZoneInfo(os.environ.get("BACKUP_TZ", "Europe/Istanbul"))

s3 = boto3.client("s3")
cognito = boto3.client("cognito-idp", region_name=REGION)


def _list_user_pools():
    pools = []
    for page in cognito.get_paginator("list_user_pools").paginate(MaxResults=60):
        pools.extend(page["UserPools"])
    return pools


def _list_users(pool_id):
    users = []
    for page in cognito.get_paginator("list_users").paginate(UserPoolId=pool_id):
        users.extend(page["Users"])
    return users


def _list_groups(pool_id):
    groups = []
    try:
        for page in cognito.get_paginator("list_groups").paginate(UserPoolId=pool_id):
            groups.extend(page["Groups"])
    except ClientError as e:
        # User pools without groups raise ResourceNotFoundException; non-fatal.
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            logger.info("Pool %s has no groups", pool_id)
        else:
            logger.warning("list_groups failed for %s: %s", pool_id, e)
    return groups


def _backup_pool(pool, now):
    pool_id = pool["Id"]
    pool_name = pool["Name"]
    timestamp = now.strftime("%Y%m%d")
    date_path = now.strftime("%Y/%m/%d")

    backup_data = {
        "UserPool": cognito.describe_user_pool(UserPoolId=pool_id)["UserPool"],
        "Users": _list_users(pool_id),
        "Groups": _list_groups(pool_id),
    }

    s3_key = f"{date_path}/{pool_name}_{timestamp}.json"
    s3.put_object(
        Bucket=BACKUP_BUCKET,
        Key=s3_key,
        Body=json.dumps(backup_data, default=str, indent=2),
        ContentType="application/json",
    )
    logger.info("Backed up pool %s (%d users, %d groups) -> s3://%s/%s",
                pool_name, len(backup_data["Users"]), len(backup_data["Groups"]),
                BACKUP_BUCKET, s3_key)


def lambda_handler(event, context):
    now = datetime.now(TZ)
    pools = _list_user_pools()
    failed = []
    for pool in pools:
        try:
            _backup_pool(pool, now)
        except Exception as e:
            logger.exception("Backup failed for pool %s", pool.get("Name"))
            failed.append({"pool": pool.get("Name"), "error": str(e)})

    return {
        "statusCode": 207 if failed else 200,
        "body": json.dumps({
            "message": f"Backed up {len(pools) - len(failed)}/{len(pools)} user pools",
            "failed": failed,
        }),
    }
