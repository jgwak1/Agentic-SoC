import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# configure_webhook_connector.py
#         │
#         │ HTTP requests
#         ▼
# Kibana API
#         │
#         ├─ GET
#         │   Check whether the webhook connector already exists
#         │
#         ├─ POST
#         │   Create the connector if it does not exist
#         │
#         ├─ PUT
#         │   Update the connector if it already exists
#         │
#         └─ POST .../_execute
#             Test the connector
#                 │
#                 ▼
#         Elastic Webhook Connector
#                 │
#                 ▼
#           ngrok public URL
#                 │
#                 ▼
#         FastAPI /webhooks/elastic

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"

CONNECTOR_ID = "agentic-soc-webhook"
CONNECTOR_NAME = "Agentic SOC Webhook"


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


config = load_config()

KIBANA_URL = config["kibana_url"].rstrip("/")
API_KEY = config["api_key"]
WEBHOOK_URL = config["webhook_url"]
WEBHOOK_SECRET = config["webhook_secret"]


def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")

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
            f"Elastic API failed: HTTP {exc.code}\n{message}"
        ) from exc


def connector_exists():
    try:
        request(
            "GET",
            f"/api/actions/connector/{CONNECTOR_ID}",
        )
        return True
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return False
        raise


def configure_connector():
    config = {
        "url": WEBHOOK_URL,
        "method": "post",
        "hasAuth": False,
        "headers": {
            "Content-Type": "application/json",
            "X-Agentic-SOC-Token": WEBHOOK_SECRET,
        },
    }

    if connector_exists():
        request(
            "PUT",
            f"/api/actions/connector/{CONNECTOR_ID}",
            {
                "name": CONNECTOR_NAME,
                "config": config,
            },
        )
        print("Webhook connector updated.")

    else:
        request(
            "POST",
            f"/api/actions/connector/{CONNECTOR_ID}",
            {
                "name": CONNECTOR_NAME,
                "connector_type_id": ".webhook",
                "config": config,
            },
        )
        print("Webhook connector created.")

def test_connector():
    result = request(
        "POST",
        f"/api/actions/connector/{CONNECTOR_ID}/_execute",
        {
            "params": {
                "body": json.dumps({
                    "alert_id": "elastic-connector-test"
                })
            }
        },
    )

    print("Connector test result:")
    print(json.dumps(result, indent=2))


def main():
    configure_connector()
    test_connector()


if __name__ == "__main__":
    main()