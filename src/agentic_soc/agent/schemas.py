from pydantic import BaseModel, Field, model_validator
from pprint import pprint

from typing import Literal

class QuestionAssessment(BaseModel):
     status : Literal["resolved", "blocked", "investigable", "not_needed"]
     reason: str = Field(min_length=1)
     
class FactAssessment(BaseModel):
    follow_up_questions: list[str]
    reason: str = Field(min_length=1)

class GapAssignment(BaseModel):
     existing_question_id: str | None = None
     new_question : str | None = None

     @model_validator(mode = "after")
     def validate_assignment(self):
          # Each evidence-gap must link to an existing question OR propose a new question
          # Invalid: Planner selected both options
          if self.existing_question_id and self.new_question:
               pprint({ "existing_question_id": self.existing_question_id,
                        "new_question": self.new_question })
               raise ValueError("Both existing_question_id and new_question were provided. Choose one and set the other to null.")
          if not self.existing_question_id and not self.new_question:
               pprint({ "existing_question_id": self.existing_question_id,
                        "new_question": self.new_question })
               raise ValueError("Neither existing_question_id nor new_question was provided. Supply an existing question ID or a new question.")

          return self

class InvestigationPlan(BaseModel):
      should_stop: bool

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


      stop_reason: str | None = Field(
          description=(
              "Explain in plain language why the investigation should stop. "
              "Use null when continuing."
          )
      )

      stop_basis: Literal["sufficient_evidence", "no_actionable_path"] | None = Field(
          description=(
              "The stopping category: sufficient_evidence or no_actionable_path. "
              "Use null when continuing."
          )
      )

      question_assessments: dict[str, QuestionAssessment] = Field(
          description=(
              "Assess every tracked question ID when stopping. "
              "Use an empty object when continuing."
          )
      )

      questions_to_block : dict[str, str] = Field(
           default_factory = dict,
           description = (
                "Map existing active question IDs to reasons they cannot be "
                "meaningfully investigated with available tools. "
                "Return an empty dictionary if none."
           )
      )

      fact_assessments: dict[str, FactAssessment] = Field(
          description=(
              "Assess every supplied fact ID. Generate follow-up questions, "
              "or explain why no additional question is needed."
          )
      )      

      gap_assignments: dict[str, GapAssignment] = Field(
          #  default_factory = dict,
           description = (
                "For each supplied evidence Gap ID, either link it to an "
                "existing active question ID or propose a new question."
           )
      )


      @model_validator(mode="after")
      def validate_plan(self):

            if self.should_stop and not self.stop_reason:
                  raise ValueError("Stopping requires a reason.")

          #   if not self.should_stop and not all([
          #         self.current_question,
          #         self.evidence_needed,
          #         self.action_intent,
          #         self.tool_name,
          #   ]):

            if not self.should_stop:
               required_fields = [
                 "current_question",
                 "evidence_needed",
                 "action_intent",
                 "tool_name",
               ]
                  
               #    raise ValueError("Continuing requires a complete plan.")

               missing = [
                    field for field in required_fields
                    if not getattr(self, field)
                  ]

               if missing:
                      raise ValueError(
                         f"Continuing plan is missing: {missing}"
                         )

            if self.should_stop and self.stop_basis is None:
                 raise ValueError("Stopping requires a stop_basis.")


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
   
   current_question_answer : str | None = Field(
        default = None,
        description = "Answer to the current question based on evidence; null if unresolved."
   )
   current_question_evidence: list[str] = Field(
        default_factory = list,
        description = "Specific evidence supporting the answer; empty if unresolved."
   )



   @model_validator(mode="after")
   def validate_review(self):
      if not self.current_question_resolved: 
         if not (self.open_questions or self.evidence_gaps):
             raise ValueError("An unresolved question requires either an open question or evidence gap.")

      # A question can be marked as resolved only when the Reviewer provides 
      #  both its answer and supporting evidence
      if self.current_question_resolved:
           if not self.current_question_answer or not self.current_question_evidence:
                raise ValueError("A resolved question requires both an answer and supporting evidence.")

      return self