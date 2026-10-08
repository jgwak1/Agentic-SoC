from typing import Annotated, TypedDict, Any, Required

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class InvestigationState(TypedDict, total = False):
      alert_id : Required[str]
      alert : dict[str, Any]
      messages: Annotated[ list[AnyMessage], add_messages ]
 
      plan: dict[ str, Any ] | None
      evidence_review: dict[ str, Any] | None

      verdict: str