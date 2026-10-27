from typing import Annotated, TypedDict, Any, Required

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from operator import add


class CompletedQuestion(TypedDict):
      question: str
      answer : str 
      evidence : list[str]


class InvestigationState(TypedDict, total = False):
      alert_id : Required[str]
      alert : dict[str, Any]
      messages: Annotated[ list[AnyMessage], add_messages ]

      questions: list[str]

      active_questions: dict[str, str] # question ID → question text.
      completed_questions: dict[str, CompletedQuestion] # question ID → question, answer, and evidence.
      next_question_number : int # number to use when assigning a new question ID, so IDs are not reused.

      plan: dict[ str, Any ] | None
      evidence_review: dict[ str, Any] | None

      verdict: str