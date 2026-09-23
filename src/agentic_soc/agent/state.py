from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class InvestigationState(TypedDict):
      alert_id : str
      alert : dict
      messages: Annotated[ list[AnyMessage], add_messages ]
      verdict: str