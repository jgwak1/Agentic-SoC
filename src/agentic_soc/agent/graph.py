from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage 
from langgraph.prebuilt import ToolNode
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from pprint import pprint

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
# available_tools = "\n".join([f"- {t.name}: {t.description}" for t in tools])

available_tools = "\n\n".join(
    f"Tool: {t.name}\n"
    f"Description: {t.description}\n"
    f"Parameters: {json.dumps(t.args_schema.model_json_schema(), indent=2)}"
    for t in tools
)

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
              "blocked_questions": {},
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
     blocked = state["blocked_questions"]

     # Collect existing question texts to avoid adding duplicates.
     existing = set(active.values())
     existing.update( q["question"] for q in completed.values() )
     existing.update( q["question"] for q in blocked.values() )

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

    # evidence_review = state.get("evidence_review", {})
    # facts = {
    #     **{
    #         f"alert.{name}": value
    #         for name, value in context.items()
    #         if name != "rule_investigation_guide" and value is not None
    #     },
    #     **{
    #         f"f{i+1}": fact
    #         for i, fact in enumerate(
    #             evidence_review.get("established_facts", [])
    #         )
    #     },
    # }


    evidence_review = state.get("evidence_review") or {}
    # Assess the original alert fields only in the first Planner round,
    # instead of redundantly reassessing them across all rounds.
    # In later rounds, assess newly established facts from Reviewer (i.e., evidence_review["established_facts"]).
    # The original alert remains available to Planner as context in every round.
    facts = {}

    # First round: include original alert fields for assessment.
    if state.get("plan") is None:
        facts.update({
            f"alert.{name}": value
            for name, value in context.items()
            if name != "rule_investigation_guide" and value is not None
        })
    # Include facts established by Reviewer from previous tool results.
    facts.update({
        f"f{i+1}": fact
        for i, fact in enumerate(
            evidence_review.get("established_facts", [])
        )
    })

    # Assign an ID (g1, g2, ...) to each evidence gap reported by Reviewer
    gaps_sent = {
         f"g{i+1}" : gap for i, gap in enumerate(evidence_review.get("evidence_gaps", []))
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

    gap_schema = plan_schema["properties"]["gap_assignments"]
    gap_type = gap_schema["additionalProperties"]

    gap_schema.update(
     properties={gap_id: gap_type for gap_id in gaps_sent},
     required=list(gaps_sent),
     additionalProperties=False,
     )

    round_planner_llm = base_llm.with_structured_output(
        plan_schema, method="json_schema"
    )

    # questions = list(dict.fromkeys([
    #     *state.get("questions", []),
    #     *evidence_review.get("open_questions", []),
    # ]))

    prompt = PLANNER_PROMPT.format(
        context=json.dumps(context, indent=2),
        evidence_review=json.dumps(evidence_review, indent=2),
        available_tools=available_tools,
    )


    # Send these gap-IDs and their corresponding evidence-gaps to the Planner
    prompt += "\n\nEvidence gaps to assign:\n" + json.dumps(gaps_sent, indent=2)


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


    for label, records in (
          ("FACTS", facts),
          ("EVIDENCE GAPS", gaps_sent),
          ("ACTIVE QUESTIONS", questions_sent),
          ("COMPLETED QUESTIONS", state["completed_questions"]),
          ("BLOCKED QUESTIONS", state["blocked_questions"]),
     ):
          print(f"\n[Planner input: {label}]")
          pprint(records, width=100, sort_dicts=False)

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

                  # Provide these as reference, for planning
                  + "\n\nCompleted questions (reference only; do not investigate again):\n"
                  + json.dumps(state["completed_questions"], indent=2)
                  + "\n\nBlocked questions (reference only; do not investigate again):\n"
                  + json.dumps(state["blocked_questions"], indent=2)

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

            # Validate Planner's blocking decisions before updating the state.
            blocked_requests = plan.questions_to_block

            # Planner may block only questions that Python actually sent.
            unknown_ids = set(blocked_requests) - set(questions_sent)

            if unknown_ids:
                 raise OutputParserException(
                      f"Cannot block unknown or inactive questions: {sorted(unknown_ids)}"
                 )

            # Each blocked question must have a meaningful reason.
            if any(not reason.strip() for reason in blocked_requests.values()):
                 raise OutputParserException(
                      "Each blocked question requires a non-empty reason."
                 )

            # Planner cannot select Q2 for investigation while also blocking Q2.
            if not plan.should_stop:
                 if plan.current_question.strip() in {
                      questions_sent[qid] for qid in blocked_requests
                 }:
                    raise OutputParserException(
                         "Planner selected a question it also marked as blocked."
                    )

            # Check that Planner handled every supplied gap (g1, g2, ...).
            expected_gap_ids = set(gaps_sent)
            returned_gap_ids = set(plan.gap_assignments)

            if returned_gap_ids != expected_gap_ids:
                 raise OutputParserException(
                      "Gap assignments do not match the gaps supplied to the Planner. "
                      f"Missing: {sorted(expected_gap_ids - returned_gap_ids)}. "
                      f"Unexpected: {sorted(returned_gap_ids - expected_gap_ids)}"
                 )
            # If a gap is linked to an existing question, that question must be active.
            for gap_id, assignment in plan.gap_assignments.items():

                 # if a gap was assigned to an existing question
                 if assignment.existing_question_id is not None: 

                      # if that question-id actually doesn't correspond to one of the active questions (questions_sent)
                      if assignment.existing_question_id not in questions_sent:  
                           raise OutputParserException(
                                f"{gap_id} refers to an unknown or inactive question: "
                                f"{assignment.existing_question_id}"
                           )


            # All planner response checks have passed. 
            # Now, collect new questions generated by Planner
            new_questions = []

            # Collect new questions generated from fact assessments.
            for assessment in plan.fact_assessments.values():
                 new_questions.extend(assessment.follow_up_questions)

            # Collect new questions proposed to address evidence gaps.
            for assignment in plan.gap_assignments.values():
                 if assignment.new_question:
                      new_questions.append( assignment.new_question )

            # Include Planner's selected question if it is new.
            if plan.current_question:
                 new_questions.append(plan.current_question)

            # Assign IDs to newly generatd questions without modifying the original state
            updated_active, updated_next_num = register_questions( state, new_questions )

            # Match Planner's selected question to its permanent ID
            plan_data = plan.model_dump()

            # Connect each evidence gap to the permanent ID of its assigned question.
            gap_question_ids = {}

            for gap_id, assignment in plan.gap_assignments.items():

                # Case 1: Planner linked the gap to an existing question (e.g., Q2)
                if assignment.existing_question_id is not None:
                     question_id = assignment.existing_question_id

                # Case 2: Planner proposed a new quesiton for the gap                 
                #   find the qid (e.g., Q3) already assigned by register_questions()
                else:
                     question_id = None
                     for qid, question_text in updated_active.items():
                          if question_text == assignment.new_question.strip():
                               question_id = qid
                               break
                          
                # Reject the links to non-existent or blocked questions
                if question_id not in updated_active or question_id in plan.questions_to_block:
                     raise OutputParserException(f"{gap_id} is not linked to a valid active question.")

                # Save the mapping (e.g., G1 -> Q2)
                gap_question_ids[gap_id] = question_id
            
            # Include the gap-to-question mappings in the plan saved by LangGraph 
            plan_data["gap_question_ids"] = gap_question_ids


            if not plan.should_stop:

                # Python finds the ID for plan.current_question and stores that ID alongside the plan.
                # No need to rely on Qwen which could hallucinate
                selected_id = next( (qid for qid, question in updated_active.items() \
                                      if question == plan.current_question.strip()), None )
                
                # Retry Planner later if its selected question has no registered ID.
                if selected_id is None:
                     raise OutputParserException("Planner's selected question wasn't registered")
                
                plan_data["current_question_id"] = selected_id

            # Move accepted blocked questions from active to blocked records.
            updated_blocked = state["blocked_questions"].copy()

            for qid, reason in blocked_requests.items():
                    updated_blocked[qid] = {
                        "question": updated_active.pop(qid),
                        "reason": reason.strip(),
                    }
            

          #   print("[Planner] Plan:")
          #   print(plan_data)

            print("\n[Planner] Plan:")
            pprint(plan_data, width=100, sort_dicts=False)


            return {
                # "plan": plan.model_dump(),
                # "questions": questions,
                "plan": plan_data,
                "active_questions": updated_active,
                "next_question_number": updated_next_num,
                "blocked_questions": updated_blocked,
                # don't need to return completed_questions here as LangGraph preserves that field.
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
     #  print("tool_calls:", response.tool_calls)
      print("tool_calls:")
      pprint(response.tool_calls, width=100, sort_dicts=False)

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

      # Debug
      print("\n[Actual tool call]")
      pprint(tool_call, width=100, sort_dicts=False)
      print("\n[Actual tool results]")
      try:
          tool_data = json.loads(tool_result)
      except json.JSONDecodeError:
          tool_data = tool_result
      pprint(tool_data, width=100, sort_dicts=False)


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
                print("[Reviewer] Evidence review:")
                pprint(review.model_dump(), width=100, sort_dicts=False)

            #     return {"evidence_review": review.model_dump()}

                # questions = list(dict.fromkeys([
                #     *state.get("questions", []),
                #     *review.open_questions,
                # ]))

                # return {
                #     "evidence_review": review.model_dump(),
                #     "questions": questions,
                # }


                # Register new unresolved questions suggested by Reviewer
                updated_active, updated_next_num = register_questions(
                     state, review.open_questions
                )
                # Copy completed records before making changes. 
                updated_completed = state["completed_questions"].copy()

                # Retrieve permanent-ID of the question investigated in this round.
                current_qid = plan["current_question_id"]
                if current_qid not in updated_active:
                     raise OutputParserException(
                          f"Current question {current_qid} is missing from active_questions."
                     )
                if review.current_question_resolved:
                    # Move the answered question from active to completed, 
                    # preserving its answer and supporting evidence.
                    updated_completed[current_qid] = {
                         "question": updated_active.pop(current_qid),
                         "answer": review.current_question_answer,
                         "evidence": review.current_question_evidence
                    }
                return {
                        "evidence_review" : review.model_dump(),
                        "active_questions": updated_active,
                        "completed_questions": updated_completed,
                        "next_question_number": updated_next_num
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
