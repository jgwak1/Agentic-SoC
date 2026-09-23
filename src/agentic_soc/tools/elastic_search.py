from langchain_core.tools import tool
from agentic_soc.elastic.client import ElasticClient


@tool
def search_cloudtrail(
   start_time : str,
   end_time : str,
   event_action : str | None = None,
   access_key  : str | None = None, 
) -> list[dict]:
   """ Search AWS CloudTrail events in Elasticsearch for a time range and optional filters."""

   filters = [
      {"range": {"@timestamp": {"gte": start_time, "lte": end_time}}}  
   ]

   # optional filters to determined by LLM-agent
   if event_action:
      filters.append({"term": {"event.action": event_action}})

   if access_key:
      filters.append({"term": {"aws.cloudtrail.user_identity.access_key_id": access_key}})

   response = ElasticClient().search_cloudtrail({
      "size": 20, # limit to 20 
      "query": {"bool": {"filter": filters}}
   })

   events = []
   for hit in response["hits"]["hits"]:
      event = hit["_source"]

      events.append({
         "timestamp": event.get("@timestamp"),
         "action": event.get("event", {}).get("action"),
         "actor": event.get("user", {}).get("name"),
         "target": event.get("user", {}).get("target", {}).get("name"),
         "source_ip": event.get("source", {}).get("ip"),
         "access_key": (
                        event.get("aws", {})
                        .get("cloudtrail", {})
                        .get("user_identity", {})
                        .get("access_key_id")
         ),
      })

   return events

