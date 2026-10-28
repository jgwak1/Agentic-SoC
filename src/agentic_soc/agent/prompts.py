'''
Prompt Design Guidelines
- General-purpose: Applicable across different scenarios and tools.
- No hardcoding: No scenario-specific logic or expected answers.
- No hacks or overfitting: Not patching of prompts to fix individual failures.
'''

# baseline
# INVESTIGATOR_PROMPT = """Analyze this security alert.

# Use only the provided evidence.
# If additional CloudTrail evidence is needed, use the available tool.
# Do not query evidence already present in the alert.
# Use tools to gather new evidence that can distinguish competing hypotheses.

# Alert:
# {context}
# """

# Dynamic ReACT-style prompt
# INVESTIGATOR_PROMPT = """
# Analyze this security alert using only the available evidence.

# If additional CloudTrail evidence is needed, use the available tools.
# Do not query evidence that is already sufficiently established by the alert.

# At each investigation step:
# - Identify the most useful unresolved question based on all evidence seen so far.
# - Choose a tool query that can materially reduce that uncertainty.
# - After receiving tool evidence, determine what the result establishes and what remains unknown.
# - Revise the next investigation step based on the new evidence; do not stay committed to earlier questions if the evidence suggests a better direction.
# - Do not treat the result of a narrowly filtered query as evidence that other activity does not exist.

# Use tools to gather new evidence that can distinguish competing hypotheses.

# Alert:
# {context}
# """


PLANNER_PROMPT = """
Plan the next step of the security investigation using only the available evidence.

Actively examine and leverage all accumulated evidence, including established
facts, entities, relationships, and new findings.

Consider alternative hypotheses and investigation directions rather than
remaining committed to the current question.

Plan one focused, actionable investigation step at a time.

Choose one unresolved question that offers high information value
and can be meaningfully investigated using an available tool.

Describe:
- the question to investigate,
- what evidence is missing,
- what investigation action should be taken,
- which available tool should be used.

Describe the intended action in plain language. Do not generate tool arguments.

If an investigation direction cannot be pursued with the available tools,
reassess other unresolved questions and alternative investigation paths.

Before stopping, evaluate whether any remaining question can be
meaningfully investigated using the available tools.

The inability to resolve one question does not justify terminating
the entire investigation.

Set should_stop to true only when:
- the available evidence is sufficient for a final verdict, or
- no available tool can meaningfully investigate any remaining question.

When stopping because no useful investigation remains, identify the plausible alternative directions considered. 
Explain why each is already resolved or cannot be investigated with the available tools. 
An inability to answer the current question is insufficient justification.

If should_stop is false, all four planning fields must be provided:
current_question, evidence_needed, action_intent, and tool_name.

If should_stop is true, stop_reason must be provided.
The other planning fields may be null.

Treat rule_investigation_guide as reference guidance, not as observed evidence.

Evidence gap handling:
- For EVERY ID in "Evidence gaps to assign", return an entry in gap_assignments.
- Either link the gap to an existing active question using existing_question_id,
  or propose a new investigation question using new_question.
- For each gap, fill exactly one of existing_question_id or new_question, and set the other to null.
- Use only question IDs supplied under "Tracked questions".
- If no evidence gaps are supplied, return an empty dictionary.

For individual questions that cannot be meaningfully investigated further:
- Report their existing question IDs and reasons in questions_to_block.
- Use only IDs provided under "Tracked questions".
- Do not mark a question blocked merely because one query failed;
  consider whether another useful investigation approach exists.
- Do not select a question being blocked as current_question.
- Use an empty dictionary if no questions should be blocked.

Individual questions can be blocked even when should_stop is false
and the overall investigation continues.

When should_stop is true:
- Set stop_basis to "sufficient_evidence" or "no_actionable_path".
- In question_assessments, use every tracked question ID as a key.
- For each question, provide a status and an evidence-grounded reason:
  - resolved: available evidence answers the question.
  - blocked: available tools cannot meaningfully investigate it.
  - investigable: an available tool can gather useful missing evidence.
  - not_needed: answering it is unnecessary for the supported final verdict.
- An unsuccessful query alone does not establish that a question is blocked.
- With "no_actionable_path", every question must be resolved or blocked.
- Use "not_needed" only with "sufficient_evidence", explaining why the
  unanswered question is unnecessary for the final verdict.

  Before selecting the next question or deciding to stop, assess EVERY
entry in "Facts to assess", using its exact ID in fact_assessments.

For each fact:
- Examine its entities, identifiers, relationships, and implications.
- Generate unanswered follow-up questions arising from that fact,
  including questions arising from its relationship with other facts.
- If no additional question is needed, return an empty list and explain why.
- Do not omit a fact because it is unrelated to the current question.

Also consider additional hypotheses suggested by rule guidance and
security knowledge. Questions are not restricted to the supplied facts.

After this assessment, if should_stop is false, select one actionable investigation question.
Reuse an existing tracked question's exact wording when selecting it.

Question selection:
- "Tracked questions" contains active questions available for investigation.
- Select an active question, or propose a genuinely new question if needed.
- "Completed questions" contains previously answered questions and evidence.
  Use them as reference, but do not investigate or regenerate those questions.
- "Blocked questions" contains questions that cannot currently be investigated.
  Use them as reference, but do not select or regenerate those questions.

Alert:
{context}

Latest evidence review:
{evidence_review}

Available tools:
{available_tools}
"""



EXECUTOR_PROMPT = """
Execute the current investigation plan using the available tools.

Translate the planner's question and action intent into one valid tool call
that meaningfully addresses the investigation objective.

Requirements:
- faithfully follow the planner's investigation objective,
- use only tools and arguments defined by the available tool schemas,
- ground factual values and identifiers in the available evidence,
- select appropriate execution parameters based on the investigation objective,
- avoid unnecessary constraints that limit relevant evidence,
- do not substitute a different investigation objective.

If the plan cannot be executed with the available tools,
do not fabricate a tool call.


Alert:
{context}

Current plan:
{plan}

Latest evidence review:
{evidence_review}
"""




REVIEWER_PROMPT = """
Review the latest tool result using only the available evidence.

Maintain a detailed, cumulative record of all investigation-relevant evidence
from the original alert, previous reviews, and tool results.

Preserve important facts, entities, identifiers, relationships, and findings,
even when they are unrelated to the current investigation question.
Do not discard previously established evidence or replace concrete findings
with vague summaries.

Determine:
- what facts are established by the result,
- whether the current question was answered,
- what questions remain unresolved,
- what new questions arise from the observed evidence,
- what evidence is still missing.

Distinguish observed facts from interpretations and uncertainties.
Do not draw conclusions beyond the scope of the available evidence.
Do not choose the next investigation action or generate a tool call.

If current_question_resolved is false, provide at least one
open_question or evidence_gap.

For the current investigation question:
- If current_question_resolved is true, provide:
  - current_question_answer: the answer supported by the evidence.
  - current_question_evidence: specific evidence supporting that answer.
- If current_question_resolved is false, set:
  - current_question_answer: null
  - current_question_evidence: []

Alert:
{context}

Current plan:
{plan}

Previous evidence review:
{previous_review}

Latest tool call:
{tool_call}

Latest tool result:
{tool_result}
"""



FINAL_VERDICT_PROMPT = """
Produce the final investigation verdict.

Use only the available alert and investigation evidence.

Verdict must be one of:
- Benign
- Malicious
- Suspicious
- Insufficient Evidence

Briefly state the supporting evidence and limitations.

Alert:
{context}

Evidence review:
{evidence_review}

Planner stop reason:
{stop_reason}
"""
