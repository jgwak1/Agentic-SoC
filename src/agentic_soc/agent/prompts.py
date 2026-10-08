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

Choose one unresolved question that would most reduce uncertainty.
Describe:
- what evidence is missing,
- what should be investigated next,
- which available tool should be used, if any.

Describe the intended action in plain language. Do not generate tool arguments.

Set should_stop to true only when:
- the available evidence is sufficient for a final verdict, or
- no available tool can meaningfully reduce the remaining uncertainty.

Alert:
{context}

Latest evidence review:
{evidence_review}

Available tools:
{available_tools}
"""


EXECUTOR_PROMPT = """
Execute the current investigation plan using the available tools.

Use the planner's question and action intent to produce one valid tool call.

Requirements:
- use only tools and arguments defined by the available tool schemas,
- use only values supported by the available evidence,
- do not invent argument names or values,
- do not add unnecessary filters.

If the plan cannot be executed with the available tools, do not fabricate a tool call.

Alert:
{context}

Current plan:
{plan}

Latest evidence review:
{evidence_review}
"""


REVIEWER_PROMPT = """
Review the latest tool result using only the available evidence.

Determine:
- what facts are established by the result,
- whether the current question was answered,
- what questions remain unresolved,
- what evidence is still missing.

Preserve previously established facts that remain supported.
Do not treat an empty or narrowly filtered result as proof that unrelated activity does not exist.
Do not choose the next investigation action or generate a tool call.

Alert:
{context}

Current plan:
{plan}

Previous evidence review:
{previous_review}

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
