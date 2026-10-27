from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage 
from langgraph.prebuilt import ToolNode
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

MAX_PLAN_ATTEMPTS = 3
MAX_REVIEW_ATTEMPTS = 3

from agentic_soc.agent.state import InvestigationState
from agentic_soc.agent.llm import base_llm, reviewer_llm
from agentic_soc.agent.schemas import InvestigationPlan
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
      return {"alert": client.get_alert(state["alert_id"]),
              "active_questions": {},    # no questions have been registered yet.
              "completed_questions": {}, # nothing has been answered yet.
              "next_question_number": 1, # first question added will receive ID q1.
              }


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

def register_questions( state: InvestigationState, new_questions: list[str]):
     
     # Work on a copy so new questions (e.g., Q3) aren't saved immediately.
     #  Python first checks whether Planner's reply meets the requirements.
     #  If plan.should_stop is True, Planner must also report the status
     #  of every existing question (answered, still investigable, etc.).
     #  If any check fails, discard the copy and later retry the Planner call. Otherwise, save the new questions.
     active = state["active_questions"].copy()
     
     completed = state["completed_questions"]
     next_num = state["next_question_number"]

     # Collect existing question texts to avoid adding duplicates.
     existing = set(active.values())
     existing.update( q["question"] for q in completed.values() )

     for question in new_questions:
          question = question.strip()

          # Skip empty questions or questions already active or completed 
          #  (naive exact duplicate check; doesn't handle paraphrasing of semantically same question)
          if not question or question in existing:
               continue

          # Assign a permanent ID (q1, q2, ...) to each new question.
          active[f"q{next_num}"] = question
          existing.add(question)
          next_num += 1

     # Return updated values without modifying the original state.
     return active, next_num



# TODO (Future): Support parallel investigation of multiple questions.
# Currently, Planner selects one current_question per round.
# Later, LangGraph could investigate Q1, Q2, Q3 simultaneously rather than sequentially.
# Each parallel investigation must preserve its question ID so Python can
# associate tool results, Reviewer findings, and status updates with the correct question.
# Implement after the sequential workflow is stable.
def planner(state: InvestigationState):
    print("\n[Planner] Planning next investigation step...")
    alert = state["alert"]
    context = build_alert_context(alert)
    context["rule_investigation_guide"] = alert.get("kibana.alert.rule.note")

    evidence_review = state.get("evidence_review", {})

    facts = {
        **{
            f"alert.{name}": value
            for name, value in context.items()
            if name != "rule_investigation_guide" and value is not None
        },
        **{
            f"f{i+1}": fact
            for i, fact in enumerate(
                evidence_review.get("established_facts", [])
            )
        },
    }

    # Fix each round's fact IDs in the generation schema.
    plan_schema = InvestigationPlan.model_json_schema()
    assessment_schema = plan_schema["properties"]["fact_assessments"]
    assessment_type = assessment_schema["additionalProperties"]
    assessment_schema.update(
        properties={fact_id: assessment_type for fact_id in facts},
        required=list(facts),
        additionalProperties=False,
    )
    round_planner_llm = base_llm.with_structured_output(
        plan_schema, method="json_schema"
    )

    questions = list(dict.fromkeys([
        *state.get("questions", []),
        *evidence_review.get("open_questions", []),
    ]))

    prompt = PLANNER_PROMPT.format(
        context=json.dumps(context, indent=2),
        evidence_review=json.dumps(evidence_review, indent=2),
        available_tools=available_tools,
    )

    guide = context["rule_investigation_guide"]
    print(
        "[Planner] Guide included:",
        bool(guide) and json.dumps(guide) in prompt,
    )

    # Keep a fixed copy of the questions sent to Planner.
    # Even if Planner newly suggests Q3, only the original Q1 and Q2
    # should be checked when validating this reply 
    #   (i.e., when plan.should_stop=True, Python checks whether Planner reported
    #          an investigation status for EACH original question (Q1 and Q2),
    #          indicating whether it is resolved, blocked, or still investigable.
    #          When plan.should_stop=False, Python skips this question-status check).
    # (Later, we could use separate LLM calls for question assessment and generation.) 
    questions_sent = state["active_questions"].copy()

    for attempt in range(MAX_PLAN_ATTEMPTS):
        try:

            plan = round_planner_llm.invoke([
            HumanMessage(
                  prompt
                  + "\n\nFacts to assess:\n"
                  + json.dumps(facts, indent=2)
                #   + "\n\nTracked questions:\n"
                #   + json.dumps(
                #         {f"q{i+1}": q for i, q in enumerate(questions)},
                #         indent=2,
                  + "\n\nTracked questions:\n"
                  + json.dumps(questions_sent, indent=2)

            ),
            *state.get("messages", []),
            ])


            if plan is None:
                raise OutputParserException("No structured plan returned.")

            plan = InvestigationPlan.model_validate(plan)

            expected_fact_ids = set(facts)
            returned_fact_ids = set(plan.fact_assessments)

            if returned_fact_ids != expected_fact_ids:
                message = (
                    "Fact assessment IDs do not match the supplied facts. "
                    f"Missing IDs: {sorted(expected_fact_ids - returned_fact_ids)}. "
                    f"Unexpected IDs: {sorted(returned_fact_ids - expected_fact_ids)}."
                )
                print(
                    f"[Planner] Fact coverage attempt "
                    f"{attempt + 1}/{MAX_PLAN_ATTEMPTS}: {message}",
                    flush=True,
                )
                raise OutputParserException(message)

            # if set(plan.fact_assessments) != set(facts):
            #     raise OutputParserException(
            #         "Assess every supplied fact using exactly these IDs: "
            #         f"{list(facts)}"
            #     )

            # for assessment in plan.fact_assessments.values():
            #     for question in assessment.follow_up_questions:
            #         if question and question not in questions:
            #             questions.append(question)

            # if plan.current_question and plan.current_question not in questions:
            #     questions.append(plan.current_question)

            if plan.should_stop:
                # expected_ids = {
                #     f"q{i+1}" for i in range(len(questions))
                # }

                # Check only the original question IDs sent to Planner (e.g., Q1, Q2).
                # Newly generated questions (e.g., Q3) don't require assessment yet.                
                expected_ids = set(questions_sent)


                if set(plan.question_assessments) != expected_ids:
                    raise OutputParserException(
                        "Stopping requires an assessment for every tracked "
                        f"question, using exactly these IDs: {sorted(expected_ids)}"
                    )

                if plan.stop_basis == "no_actionable_path" and any(
                    assessment.status not in {"resolved", "blocked"}
                    for assessment in plan.question_assessments.values()
                ):
                    raise OutputParserException(
                        "An actionable question remains. Continue investigating, "
                        "or justify stopping on sufficient evidence."
                    )

            # All planner response checks have passed. 
            # Now, collect new questions generated by Planner
            new_questions = []

            for assessment in plan.fact_assessments.values():
                 new_questions.extend(assessment.follow_up_questions)

            if plan.current_question:
                 new_questions.append(plan.current_question)

            # Assign IDs to newly generatd questions without modifying the original state
            updated_active, updated_next_num = register_questions( state, new_questions )

            # Match Planner's selected question to its permanent ID
            plan_data = plan.model_dump()

            if not plan.should_stop:

                # Python finds the ID for plan.current_question and stores that ID alongside the plan.
                # No need to rely on Qwen which could hallucinate
                selected_id = next( (qid for qid, question in updated_active.items() \
                                      if question == plan.current_question.strip()), None )
                
                # Retry Planner later if its selected question has no registered ID.
                if selected_id is None:
                     raise OutputParserException("Planner's selected question wasn't registered")
                
                plan_data["current_question_id"] = selected_id


            print("[Planner] Plan:")
            print(plan_data)

            return {
                # "plan": plan.model_dump(),
                # "questions": questions,
                "plan": plan_data,
                "active_questions": updated_active,
                "next_question_number": updated_next_num
            }

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

            #     return {"evidence_review": review.model_dump()}

                questions = list(dict.fromkeys([
                    *state.get("questions", []),
                    *review.open_questions,
                ]))

                return {
                    "evidence_review": review.model_dump(),
                    "questions": questions,
                }

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
