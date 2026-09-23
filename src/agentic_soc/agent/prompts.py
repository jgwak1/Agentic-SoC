INVESTIGATOR_PROMPT = """Analyze this security alert.

Use only the provided evidence.
If additional CloudTrail evidence is needed, use the available tool.
Do not query evidence already present in the alert.
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
