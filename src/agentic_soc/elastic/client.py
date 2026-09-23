import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


class ElasticClient:
    def __init__(self):
        config = load_config()

        self.elasticsearch_url = config["elasticsearch_url"].rstrip("/")
        self.kibana_url = config["kibana_url"].rstrip("/")
        self.api_key = config["api_key"]

    def _request(self, method, url, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")

        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"ApiKey {self.api_key}",
                "Content-Type": "application/json",
                "kbn-xsrf": "true",
            },
        )

        try:
            with urlopen(request) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}

        except HTTPError as exc:
            message = exc.read().decode("utf-8")
            raise RuntimeError(
                f"Elastic request failed: HTTP {exc.code}\n{message}"
            ) from exc

    def search_elasticsearch(self, index, query):
        return self._request(
            "POST",
            f"{self.elasticsearch_url}/{index}/_search",
            query,
        )

    def search_cloudtrail(self, query):
        return self.search_elasticsearch(
            "logs-aws.cloudtrail-*",
            query,
        )

    def search_alerts(self, query):
         return self._request(
            "POST",
            f"{self.kibana_url}/api/detection_engine/signals/search",
            query,
         )


    def get_alert(self, alert_id: str) -> dict:
        body = {
            "size": 2,
            "query": {
                "bool": {
                    "should": [
                        {"term": {"_id": alert_id}},
                        {"term": {"kibana.alert.uuid": alert_id}},
                        {"term": {"kibana.alert.instance.id": alert_id}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        }

        response = self.search_alerts(body)

        hits = response.get("hits", {}).get("hits", [])

        if not hits:
            raise LookupError(f"Alert not found: {alert_id}")

        if len(hits) > 1:
            raise RuntimeError(
                f"Expected one alert for {alert_id}, found {len(hits)}"
            )

        hit = hits[0]

        return {
            "_id": hit["_id"],
            "_index": hit["_index"],
            **hit["_source"],
        }
