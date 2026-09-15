from agentic_soc.elastic.client import ElasticClient


client = ElasticClient()

result = client.search_alerts({
    "size": 5,
    "sort": [
        {
            "@timestamp": {
                "order": "desc"
            }
        }
    ],
    "query": {
        "term": {
            "kibana.alert.rule.name":
                "AWS IAM User Created Access Keys For Another User"
        }
    }
})

print(f"alert hits: {result['hits']['total']}")

for hit in result["hits"]["hits"]:
    source = hit["_source"]

    print(
        hit["_id"],
        source.get("@timestamp"),
        source.get("kibana.alert.rule.name"),
    )