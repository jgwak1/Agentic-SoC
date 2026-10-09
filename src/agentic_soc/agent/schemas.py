from pydantic import BaseModel, Field, model_validator

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

      @model_validator(mode="after")
      def validate_plan(self):

            if self.should_stop and not self.stop_reason:
                  raise ValueError("Stopping requires a reason.")

            if not self.should_stop and not all([
                  self.current_question,
                  self.evidence_needed,
                  self.action_intent,
                  self.tool_name,
            ]):
                  raise ValueError("Continuing requires a complete plan.")

            return self
               

class EvidenceReview(BaseModel):

   established_facts: list[str] = Field(
      description="The established facts supported by the tool results gathered so far."
   )

   open_questions: list[str] = Field(
      description="The questions that remain to be answered."
   )

   evidence_gaps: list[str] = Field(
      description="The missing evidence needed to answer the open questions."
   )

   current_question_resolved: bool = False

   @model_validator(mode="after")
   def validate_review(self):
      if not self.current_question_resolved: 
         if not (self.open_questions or self.evidence_gaps):
             raise ValueError("An unresolved question requires either an open question or evidence gap.")
         
      return self