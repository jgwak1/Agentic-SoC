import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"

REQUIRED_RULES = [
    "AWS IAM User Created Access Keys For Another User",
]


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


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
            "Authorization": f"ApiKey {API_KEY}",
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
    rule_ids = [
        installed[name]["id"]
        for name in REQUIRED_RULES
        if not installed[name]["enabled"]
    ]

    if not rule_ids:
        print("All required detection rules are already enabled.")
        return

    request(
        "POST",
        "/api/detection_engine/rules/_bulk_action",
        {
            "action": "enable",
            "ids": rule_ids,
        },
    )

    print(f"Enabled {len(rule_ids)} detection rule(s).")


def main():
    installed = ensure_required_rules_installed()
    enable_required_rules(installed)

    print("Detection rules ready:")

    for name in REQUIRED_RULES:
        print(f"  - {name}")


if __name__ == "__main__":
    main()