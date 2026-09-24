from langchain_core.tools import tool
from agentic_soc.elastic.client import ElasticClient

from pydantic import Field
from agentic_soc.tools.tool_validation import StrictToolInput, AWSActionName


class SearchCloudTrailInput(StrictToolInput):
   start_time: str = Field(
      description="Start of the CloudTrail event time range in ISO 8601 format."
   )
   end_time: str = Field(
      description="End of the CloudTrail event time range in ISO 8601 format."
   )
   event_action: AWSActionName | None = Field(
      default=None,
      description="Optional AWS API action name."
   )
   caller_access_key_id: str | None = Field(
      default=None,
      description="Optional access key ID of the credential that authenticated the CloudTrail event."
   )


@tool(args_schema=SearchCloudTrailInput)
def search_cloudtrail(
   start_time : str,
   end_time : str,
   event_action : str | None = None,
   caller_access_key_id  : str | None = None, 
) -> list[dict]:
   """ Search AWS CloudTrail events in Elasticsearch for a time range and optional filters."""

   filters = [
      {"range": {"@timestamp": {"gte": start_time, "lte": end_time}}}  
   ]

   # optional filters to determined by LLM-agent
   if event_action:
      filters.append({"term": {"event.action": event_action}})

   if caller_access_key_id:
      filters.append({"term": {"aws.cloudtrail.user_identity.access_key_id": caller_access_key_id}})

   response = ElasticClient().search_cloudtrail({
      "size": 20, # limit to 20 
      "query": {"bool": {"filter": filters}}
   })

   events = []
   for hit in response["hits"]["hits"]:
      event = hit["_source"]

      events.append({
         "event_time": event.get("@timestamp"), # # Time when this searched CloudTrail event occurred
         "action": event.get("event", {}).get("action"),
         "actor": event.get("user", {}).get("name"),
         "target": event.get("user", {}).get("target", {}).get("name"),
         "source_ip": event.get("source", {}).get("ip"),
         "caller_access_key_id": (
            event.get("aws", {})
            .get("cloudtrail", {})
            .get("user_identity", {})
            .get("access_key_id")
         ),
      })

   return events

