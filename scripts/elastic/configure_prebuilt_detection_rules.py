import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import base64
import json


ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"
LOCAL_ENV_FILE = ROOT / "infra" / "elastic-local" / ".env"

REQUIRED_RULES = [
    "AWS IAM User Created Access Keys For Another User",
]


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_local_elastic_password():
    with open(LOCAL_ENV_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("ES_LOCAL_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    raise RuntimeError("ES_LOCAL_PASSWORD not found.")


def get_authorization_header():
    if KIBANA_URL.startswith(("http://localhost", "http://127.0.0.1")):
        password = load_local_elastic_password()
        credentials = base64.b64encode(
            f"elastic:{password}".encode("utf-8")
        ).decode("ascii")

        return f"Basic {credentials}"

    return f"ApiKey {API_KEY}"


config = load_config()

KIBANA_URL = config["kibana_url"].rstrip("/")
API_KEY = config["api_key"]


def request(method, path, body=None):
    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = Request(
        KIBANA_URL + path,
        data=data,
        method=method,
        headers={
            # "Authorization": f"ApiKey {API_KEY}",
            "Authorization": get_authorization_header(),
            "Content-Type": "application/json",
            "kbn-xsrf": "true",
        },
    )

    try:
        with urlopen(req) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}

    except HTTPError as exc:
        message = exc.read().decode("utf-8")
        raise RuntimeError(
            f"Elastic API request failed: HTTP {exc.code}\n{message}"
        ) from exc


def get_installed_rules():
    rules_by_name = {}
    page = 1

    while True:
        query = urlencode({
            "page": page,
            "per_page": 100,
        })

        result = request(
            "GET",
            f"/api/detection_engine/rules/_find?{query}",
        )

        rules = result.get("data", [])

        for rule in rules:
            rules_by_name[rule["name"]] = rule

        total = result.get("total", 0)

        if page * 100 >= total:
            break

        page += 1

    return rules_by_name


def ensure_required_rules_installed():
    installed = get_installed_rules()

    missing = [
        name
        for name in REQUIRED_RULES
        if name not in installed
    ]

    if not missing:
        return installed

    print("Some required prebuilt rules are not installed.")
    print("Installing/updating Elastic prebuilt rules...")

    request(
        "PUT",
        "/api/detection_engine/rules/prepackaged",
    )

    installed = get_installed_rules()

    missing = [
        name
        for name in REQUIRED_RULES
        if name not in installed
    ]

    if missing:
        raise RuntimeError(
            f"Required rules are still missing: {missing}"
        )

    return installed


def enable_required_rules(installed):
    disabled_rules = [
        installed[name]
        for name in REQUIRED_RULES
        if not installed[name]["enabled"]
    ]

    if not disabled_rules:
        print("All required detection rules are already enabled.")
        return

    is_local = KIBANA_URL.startswith(
        ("http://localhost", "http://127.0.0.1")
    )

    if is_local:
        # Local Elastic 9.5.3: bulk enable returns an incorrect
        # insufficient-privileges error, so enable rules individually.
        for rule in disabled_rules:
            request(
                "POST",
                f"/api/alerting/rule/{rule['id']}/_enable",
            )
    else:
        # Keep the existing Elastic Cloud behavior.
        request(
            "POST",
            "/api/detection_engine/rules/_bulk_action",
            {
                "action": "enable",
                "ids": [rule["id"] for rule in disabled_rules],
            },
        )

    print(f"Enabled {len(disabled_rules)} detection rule(s).")

    

def main():
    installed = ensure_required_rules_installed()
    enable_required_rules(installed)

    print("Detection rules ready:")

    for name in REQUIRED_RULES:
        print(f"  - {name}")


if __name__ == "__main__":
    main()