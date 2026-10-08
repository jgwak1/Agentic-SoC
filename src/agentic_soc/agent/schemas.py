from pydantic import BaseModel, Field

class InvestigationPlan(BaseModel):

      current_question : str | None = Field(
         default = None,
         description = "The single investigation question to address next."
      )

      evidence_needed : str | None = Field(
         default = None,
         description = "The missing evidence needed to answer the question."
      )

      action_intent : str | None = Field(
         default = None,
         description="What evidence should be gathered next, described in plain language."
      )

      tool_name : str | None = Field(
         default = None,
         description = "The tool intended to gather the evidence."
      )

      should_stop: bool
      stop_reason: str | None = None


class EvidenceReview(BaseModel):

   established_facts: list[str] = Field(
      default_factory=list,
      description="The established facts supported by the tool results gathered so far."
   )

   open_questions: list[str] = Field(
      default_factory=list,
      description="The questions that remain to be answered."
   )

   evidence_gaps: list[str] = Field(
      default_factory=list,
      description="The missing evidence needed to answer the open questions."
   )

   current_question_resolved: bool = False