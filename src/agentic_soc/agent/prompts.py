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
INVESTIGATOR_PROMPT = """
Analyze this security alert using only the available evidence.

If additional CloudTrail evidence is needed, use the available tools.
Do not query evidence that is already sufficiently established by the alert.

At each investigation step:
- Identify the most useful unresolved question based on all evidence seen so far.
- Choose a tool query that can materially reduce that uncertainty.
- After receiving tool evidence, determine what the result establishes and what remains unknown.
- Revise the next investigation step based on the new evidence; do not stay committed to earlier questions if the evidence suggests a better direction.
- Do not treat the result of a narrowly filtered query as evidence that other activity does not exist.

Use tools to gather new evidence that can distinguish competing hypotheses.

Alert:
{context}
"""

FINAL_VERDICT_PROMPT = """Produce the final investigation verdict.

Use only the available alert and investigation evidence.

Verdict must be one of:
- Benign
- Malicious
- Suspicious
- Insufficient Evidence

Briefly state the supporting evidence and limitations.
"""
