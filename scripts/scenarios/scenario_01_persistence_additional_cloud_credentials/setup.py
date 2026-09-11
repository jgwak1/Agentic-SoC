"""Prepare the role sessions, then call attacker.py. Run only in your lab."""

import json
import sys
import uuid
from pathlib import Path

import boto3

from attacker import run_attack, save_record, utc_now

# An AWS account ID is an identifier, NOT a credential.
# Committing it does not grant AWS access, but does disclose the account number.
# Never commit secret access keys, session tokens or credential files.
ACCOUNT_ID = "969445144459"
REGION = "us-east-1"
SOURCE_PROFILE = "default"
TARGET_USER = "inventory-service"
OPERATOR_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/ops-maintenance"
AUTOMATION_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/ops-automation"

# Local evaluation/cleanup metadata, not input for the investigator AI.
STATE_DIR = Path(__file__).resolve().parent / ".scenario_state"
STATE_FILE = STATE_DIR / "last_run.json"


def assume_session(source: boto3.Session, role_arn: str,
                   session_prefix: str) -> boto3.Session:
    credentials = source.client("sts").assume_role(
        RoleArn=role_arn,
        # Session names are visible in CloudTrail: keep them neutral.
        RoleSessionName=f"{session_prefix}-{uuid.uuid4().hex[:12]}",
        DurationSeconds=3600,
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=REGION,
    )


def operator_session() -> boto3.Session:
    source = boto3.Session(profile_name=SOURCE_PROFILE, region_name=REGION)
    return assume_session(source, OPERATOR_ROLE_ARN, "maintenance")


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        previous = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if previous.get("attack_start") and not previous.get("cleanup_end"):
            raise RuntimeError("Previous run is not cleaned up. Run cleanup.py first.")
        # Preserve older records for evaluation instead of overwriting them.
        STATE_FILE.replace(STATE_DIR / f"{previous['run_id']}.json")

    record = {
        "run_id": uuid.uuid4().hex,
        "account_id": ACCOUNT_ID,
        "target_user": TARGET_USER,
        "setup_start": utc_now(),
    }
    save_record(STATE_FILE, record)
    operator = operator_session()
    iam = operator.client("iam")
    user = iam.get_user(UserName=TARGET_USER)["User"]
    if user["Arn"] != f"arn:aws:iam::{ACCOUNT_ID}:user/{TARGET_USER}":
        raise RuntimeError("Unexpected target user; stopping.")

    # For this dedicated fixture, start with zero keys. Never remove old keys here.
    keys = iam.list_access_keys(UserName=TARGET_USER)["AccessKeyMetadata"]
    if keys:
        raise RuntimeError("Target already has keys. Inspect/clean up before another run.")

    automation = assume_session(operator, AUTOMATION_ROLE_ARN, "automation")
    record["setup_end"] = utc_now()
    save_record(STATE_FILE, record)
    print(f"Setup complete. Local record: {STATE_FILE}")

    # Pass the session in memory: no credential file, shell export or subprocess.
    run_attack(automation, TARGET_USER, STATE_FILE, record)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted. Check the saved run and clean up before repeating.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Do not rerun blindly; check the saved run and cleanup.py.", file=sys.stderr)
        raise SystemExit(1)
