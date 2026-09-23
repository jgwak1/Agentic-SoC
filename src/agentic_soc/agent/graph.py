from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage 
from langgraph.prebuilt import ToolNode

from agentic_soc.agent.state import InvestigationState
from agentic_soc.agent.llm import llm
from agentic_soc.agent.prompts import INVESTIGATOR_PROMPT, FINAL_VERDICT_PROMPT

from agentic_soc.elastic.client import ElasticClient
from agentic_soc.tools.elastic_search import search_cloudtrail


tools = [search_cloudtrail]
llm_with_tools = llm.bind_tools(tools)


def load_alert(state: InvestigationState):
      client = ElasticClient()
      return {"alert": client.get_alert(state["alert_id"])}


def investigator(state: InvestigationState):
      alert = state["alert"]

      context = {
         "rule": alert.get("kibana.alert.rule.name"),
         "severity": alert.get("kibana.alert.severity"),
         "timestamp": alert.get("@timestamp"),
         "action": alert.get("event.action"),
         "actor": alert.get("user.name"),
         "target": alert.get("user.target.name"),
         "source_ip": alert.get("source.ip"),
         "user_agent": alert.get("user_agent.original"),
         # "access_key": alert.get("aws.cloudtrail.response_elements"),
         "access_key": alert["aws"]["cloudtrail"]["flattened"]["response_elements"]["accessKey"]["accessKeyId"],
      }

      response = llm_with_tools.invoke([

            HumanMessage( INVESTIGATOR_PROMPT.format(context=context) ),
            *state.get("messages", []),
      ])

      print(response.tool_calls)
      return {"messages": [ response ]}

def route_after_investigator(state: InvestigationState):
      if state["messages"][-1].tool_calls:
         return "tools"
      return "final_verdict"

def final_verdict(state: InvestigationState):

      response = llm.invoke([
         *state["messages"],
         HumanMessage( content = FINAL_VERDICT_PROMPT )
      ])

      return {"verdict": response.content}


#-----------------------------------------------------------

# Graph Topology

builder = StateGraph(InvestigationState)

builder.add_node("load_alert", load_alert)
builder.add_node("investigator", investigator)
builder.add_node("tools", ToolNode(tools))
builder.add_node("final_verdict", final_verdict)


builder.add_edge(START, "load_alert")
builder.add_edge("load_alert", "investigator")

builder.add_conditional_edges(
     "investigator", route_after_investigator
)

builder.add_edge("tools", "investigator")
builder.add_edge("final_verdict", END)

graph = builder.compile()
