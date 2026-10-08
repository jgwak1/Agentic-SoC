from langchain_ollama import ChatOllama
from agentic_soc.agent.schemas import InvestigationPlan, EvidenceReview

# llm = ChatOllama(model = "qwen2.5:7b")
base_llm = ChatOllama( model="qwen3:8b", reasoning=True ) 

# wrappers where output is structured according to the InvestigationPlan and EvidenceReview schemas
planner_llm = base_llm.with_structured_output(InvestigationPlan) 
reviewer_llm = base_llm.with_structured_output(EvidenceReview)
