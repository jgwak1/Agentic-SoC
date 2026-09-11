# Scenario 01

Place this directory at `scripts/scenarios/scenario_01/` in the existing project.
The Terraform identities must already exist:

- `ops-maintenance`: assume `ops-automation`, inspect `inventory-service`, and delete its access keys.
- `ops-automation`: create an access key for `inventory-service` only.
- `inventory-service`: call `iam:ListUsers`.

## Run

From the repository root, activate your Python environment and install `boto3`:

```bash
python -m pip install boto3
python scripts/scenarios/scenario_01/setup.py
```

`setup.py` prepares both temporary role sessions and calls `attacker.run_attack()` in the same Python process. There is no separate `python attacker.py` step and no credential file or shell export. The attack code uses only the supplied role session and then the newly created user key.

The attack performs `CreateAccessKey` and uses the new key for `ListUsers(MaxItems=1)`. It does not call `AssumeRole`, `GetCallerIdentity`, or `DeleteAccessKey`. The returned user list is not printed or saved.

After verifying the actual CloudTrail events and saving the investigation results:

```bash
python scripts/scenarios/scenario_01/cleanup.py
```

Cleanup obtains a fresh operator session and deletes only the recorded key. It does not remove the IAM user, roles, or other keys. The new key is not automatically deleted or disabled by these scripts, so run cleanup even when investigation is postponed or the attack fails after creating the key.

## Local records and repeat runs

The active run is recorded in `.scenario_state/last_run.json` beside the scripts. It contains timestamps, the created key ID, request IDs, and outcomes, but no secret access key or session token. Completed/earlier records are archived when a new run starts.

Use one run at a time. Setup refuses to start another attack before cleanup and requires the dedicated user to have zero existing keys. This zero-key rule is a script guard, not the AWS key quota. It never silently deletes an existing key.

ListUsers may be retried up to six total attempts, five seconds apart, for `InvalidClientTokenId` or `AccessDenied`. IAM propagation can cause a temporary failure; persistent failure may instead indicate a permissions problem. All attempts are real requests and may appear in CloudTrail. The script does not retry CreateAccessKey automatically.

A lost CreateAccessKey response or a process/disk failure before saving its key ID can leave an unrecorded key. In that case cleanup refuses to guess: inspect the target user's keys before deleting anything or rerunning.

## Publishing and evaluation

The account ID in `setup.py` is an identifier, not an authentication credential. Publishing it does not grant access but reveals the account number. The scripts contain no embedded secret access key or session token.

Commit the Python files and this directory's `.gitignore`. Do not commit runtime records, AWS credential files, environment files containing credentials, or Terraform state. These scripts do not audit the rest of your repository or erase files already committed to Git history.

AWS-facing role/user names and STS session names do not include scenario or attacker labels. Local source code, filenames, and run records do contain experiment context: keep them out of the investigator's inputs/tools and use them only for orchestration/evaluation. Existing account resources and historical CloudTrail events are not anonymized by these scripts.

## Validation

Python syntax checks and 10 mocked tests passed. No live AWS execution was performed in the authoring environment. Actual AWS permissions, propagation, CloudTrail delivery and ingestion must still be verified in your account.

## AWS references

- Account IDs: https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-identifiers.html
- Boto3 credentials: https://docs.aws.amazon.com/boto3/latest/guide/credentials.html
- AssumeRole: https://docs.aws.amazon.com/boto3/latest/reference/services/sts/client/assume_role.html
- CreateAccessKey: https://docs.aws.amazon.com/boto3/latest/reference/services/iam/client/create_access_key.html
- ListUsers: https://docs.aws.amazon.com/boto3/latest/reference/services/iam/client/list_users.html
- IAM consistency: https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html
