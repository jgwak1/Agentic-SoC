from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage 
from langgraph.prebuilt import ToolNode
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

MAX_PLAN_ATTEMPTS = 3
MAX_REVIEW_ATTEMPTS = 3

from agentic_soc.agent.state import InvestigationState
from agentic_soc.agent.llm import base_llm, planner_llm, reviewer_llm
from agentic_soc.agent.prompts import PLANNER_PROMPT, EXECUTOR_PROMPT, REVIEWER_PROMPT, FINAL_VERDICT_PROMPT

from agentic_soc.elastic.client import ElasticClient
from agentic_soc.tools.elastic_search import search_cloudtrail

import json

tools = [search_cloudtrail]
available_tools = "\n".join([f"- {t.name}: {t.description}" for t in tools])

# print(search_cloudtrail.args_schema.model_json_schema())
# print(
#    search_cloudtrail.args_schema.model_validate({
#       "start_time": "2026-09-21T22:00:00.000Z",
#       "end_time": "2026-09-22T22:00:00.000Z",
#       "event_action": "CreateAccessKey",
#       "actor": "ops-automation",
#       "target": "inventory-service",
#    }).model_dump()
# )

executor_llm = base_llm.bind_tools(tools)


def load_alert(state: InvestigationState):
      client = ElasticClient()
      return {"alert": client.get_alert(state["alert_id"])}


def build_alert_context(alert: dict) -> dict:
      cloudtrail = alert.get("aws", {}).get("cloudtrail", {})
      flattened = cloudtrail.get("flattened", {})

      context = {
         "rule": alert.get("kibana.alert.rule.name"),
         "severity": alert.get("kibana.alert.severity"),
         "event_time": alert.get("kibana.alert.original_time"),
         "action": alert.get("event.action"),
         "actor": alert.get("user.name"),
         "target": alert.get("user.target.name"),
         "source_ip": alert.get("source.ip"),
         "user_agent": alert.get("user_agent.original"),

         # Identity that authenticated the original CloudTrail event
         "caller_access_key_id": alert.get("aws.cloudtrail.user_identity.access_key_id"),
         "principal_arn": alert.get("aws.cloudtrail.user_identity.arn"),
         "identity_type": alert.get("aws.cloudtrail.user_identity.type"),

         # Generic API request/response evidence
         "request_parameters": flattened.get("request_parameters"),
         "response_elements": flattened.get("response_elements"),
      }
      return context


def planner( state: InvestigationState ):
      print("\n[Planner] Planning next investigation step...")
      alert = state["alert"]
      context = build_alert_context(alert)

      evidence_review = state.get("evidence_review", {})

      prompt = PLANNER_PROMPT.format(
                  context = json.dumps(context, indent=2),
                  evidence_review = json.dumps(evidence_review, indent=2),
                  available_tools = available_tools,
      )

      for attempt in range(MAX_PLAN_ATTEMPTS):

         try:
            # plan = planner_llm.invoke(prompt)

            plan = planner_llm.invoke([
                  HumanMessage(prompt),
                  *state.get("messages", [])  # pass along all previous messages to the planner for context
            ])


            if plan is None:
                raise OutputParserException("No structured plan returned.")

            print("[Planner] Plan:")
            print(plan.model_dump())
      
            return {"plan": plan.model_dump()}

         except (ValidationError, OutputParserException) as e:

            if attempt == MAX_PLAN_ATTEMPTS - 1:
                 raise

            prompt += (
                        f"\n\nYour previous output failed validation:\n{e}\n"
                         "Correct the errors and regenerate the plan."
            )


def executor( state: InvestigationState):
      print("\n[Executor] Converting plan into tool call...")
      alert = state["alert"]
      context = build_alert_context(alert)

      plan = state["plan"]
      evidence_review = state.get("evidence_review", {})

      response = executor_llm.invoke([
            HumanMessage(
                  EXECUTOR_PROMPT.format(
                        context = json.dumps( context, indent=2),
                        plan = json.dumps( plan, indent = 2),
                        evidence_review = json.dumps( evidence_review, indent= 2),
                  )
            )
      ])
      print("\n[Executor]")
      print("content:", response.content)
      print("reasoning:", response.additional_kwargs.get("reasoning_content"))
      print("tool_calls:", response.tool_calls)

      if len(response.tool_calls) != 1:
         raise RuntimeError("Executor must produce exactly one tool call.")

      return {"messages": [response]}


def reviewer( state: InvestigationState):
      print("\n[Reviewer] Reviewing latest tool result...")

      alert = state["alert"]
      context = build_alert_context(alert)

      plan = state["plan"]
      previous_review = state.get("evidence_review", {})

      tool_call = state["messages"][-2].tool_calls[0] # latest tool call
      tool_result = state["messages"][-1].content # latest tool result

      prompt = REVIEWER_PROMPT.format(
                        context = json.dumps( context, indent = 2),
                        plan = json.dumps( plan, indent = 2),
                        previous_review = json.dumps( previous_review, indent = 2),
                        tool_call = json.dumps( tool_call, indent=2 ),
                        tool_result = tool_result,         
                 )
      for attempt in range(MAX_REVIEW_ATTEMPTS):

           try: 
                review = reviewer_llm.invoke([
                          HumanMessage(prompt)
                ])
                print(f"[Reviewer] Evidence review: {review.model_dump()}")

                return {"evidence_review": review.model_dump()}

           except (ValidationError, OutputParserException) as e:

                if attempt == MAX_REVIEW_ATTEMPTS - 1:
                     raise

                prompt += (
                        f"\n\nPrevious review failed validation:\n{e}\n"
                        "Correct the errors and regenerate the review."
                  )



      # review = reviewer_llm.invoke([
      #       HumanMessage(

      #       )
      # ])
      print("[Reviewer] Evidence review:")
      print(review.model_dump())
      return {"evidence_review": review.model_dump()}


def route_after_planner(state: InvestigationState):
      plan = state["plan"]

      if plan["should_stop"]:
            return "final_verdict"
      
      return "executor"


# def investigator(state: InvestigationState):
#       alert = state["alert"]
#       context = build_alert_context(alert)

#       response = base_llm.invoke([
#             HumanMessage( INVESTIGATOR_PROMPT.format(context=context) ),
#             *state.get("messages", []),
#       ])

#       print(response.tool_calls)
#       return {"messages": [ response ]}



# def route_after_investigator(state: InvestigationState):
#       if state["messages"][-1].tool_calls:
#          return "tools"

#       return "final_verdict"


def final_verdict(state: InvestigationState):
      alert = state["alert"]
      context = build_alert_context(alert)

      plan = state.get("plan", {})
      evidence_review = state.get("evidence_review", {})

      response = base_llm.invoke([
         HumanMessage( 
               FINAL_VERDICT_PROMPT.format(
                     context = json.dumps(context, indent=2),
                     evidence_review = json.dumps(evidence_review, indent=2),
                     stop_reason = plan.get("stop_reason")
               )
         )
      ])

      return {"verdict": response.content}


#-----------------------------------------------------------

# Graph Topology

builder = StateGraph(InvestigationState)

# nodes
builder.add_node("load_alert", load_alert)
# builder.add_node("investigator", investigator)
builder.add_node("planner", planner)
builder.add_node("executor", executor)
builder.add_node("tools", ToolNode(tools))
builder.add_node("reviewer", reviewer)
builder.add_node("final_verdict", final_verdict)

# edges
builder.add_edge(START, "load_alert")
builder.add_edge("load_alert", "planner")

builder.add_conditional_edges(
     source="planner", 
     path =route_after_planner,
     path_map = {"executor": "executor", 
                 "final_verdict": "final_verdict"}
)

builder.add_edge("executor", "tools")
builder.add_edge("tools", "reviewer")
builder.add_edge("reviewer", "planner")

builder.add_edge("final_verdict", END)

graph = builder.compile()
