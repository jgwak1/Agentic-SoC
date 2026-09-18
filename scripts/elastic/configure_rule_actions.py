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

CONNECTOR_ID = "agentic-soc-webhook"


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


def configure_rule_actions(installed):
    missing = [
        name
        for name in REQUIRED_RULES
        if name not in installed
    ]

    if missing:
        raise RuntimeError(
            f"Required rules are not installed: {missing}"
        )

    # Only modify rules that do not already use this connector.
    rule_ids = []

    for name in REQUIRED_RULES:
        rule = installed[name]

        connector_already_attached = any(
            action.get("id") == CONNECTOR_ID
            for action in rule.get("actions", [])
        )

        if not connector_already_attached:
            rule_ids.append(rule["id"])

    if not rule_ids:
        print("Webhook action is already attached to all required rules.")
        return

    # Per-alert actions can use {{alert.id}}.
    webhook_body = json.dumps({
        "alert_id": "{{alert.id}}"
    })

    request(
        "POST",
        "/api/detection_engine/rules/_bulk_action",
        {
            "action": "edit",
            "edit": [
                {
                    "type": "add_rule_actions",
                    "value": {
                        "actions": [
                            {
                                "id": CONNECTOR_ID,
                                "group": "default",
                                "frequency": {
                                    "summary": False,
                                    "notifyWhen": "onActiveAlert",
                                    "throttle": None,
                                },
                                "params": {
                                    "body": webhook_body,
                                },
                            }
                        ]
                    },
                }
            ],
            "ids": rule_ids,
        },
    )

    print(
        f"Webhook action attached to "
        f"{len(rule_ids)} detection rule(s)."
    )


def main():
    installed = get_installed_rules()
    configure_rule_actions(installed)

    print("Rule actions ready:")

    for name in REQUIRED_RULES:
        print(f"  - {name}")


if __name__ == "__main__":
    main()