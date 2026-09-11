"""Delete only the key recorded for the most recent run. Keep the roles/user."""

import json
import sys

from botocore.exceptions import ClientError

from attacker import save_record, utc_now   # "save_record" is a shared helper for local scenario-state bookkeeping (here, to record cleanup progress).
from setup import ACCOUNT_ID, STATE_FILE, TARGET_USER, operator_session


def main() -> None:
    if not STATE_FILE.exists():
        raise RuntimeError("No saved run. Do not guess which key to delete.")
    record = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if record.get("account_id") != ACCOUNT_ID or record.get("target_user") != TARGET_USER:
        raise RuntimeError("Saved account/user does not match this configuration.")
    if record.get("cleanup_end"):
        print("This run has already been cleaned up.")
        return

    key_id = record.get("created_access_key_id")
    if not key_id:
        if record.get("attack_start"):
            # A lost CreateAccessKey response can leave a key without a saved ID.
            raise RuntimeError("No key ID was saved. Inspect inventory-service keys before retrying.")
        print("No attack started; no scenario key needs deletion.")
        return

    record["cleanup_start"] = utc_now()
    save_record(STATE_FILE, record)
    # Obtain a fresh operator session; do not use the attacker's credentials.
    iam = operator_session().client("iam")
    try:
        result = iam.delete_access_key(UserName=TARGET_USER, AccessKeyId=key_id)
        record["delete_request_id"] = result["ResponseMetadata"]["RequestId"]
        record["cleanup_status"] = "deleted"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchEntity":
            raise
        record["cleanup_status"] = "already_absent"

    record["cleanup_end"] = utc_now()
    save_record(STATE_FILE, record)
    print("Cleanup complete. Recorded key removed; roles and user retained.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cleanup interrupted. Run cleanup.py again.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
