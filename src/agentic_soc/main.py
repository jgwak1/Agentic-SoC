import sys
import json

from pathlib import Path
from pprint import pprint

from langchain_core.messages import messages_to_dict
from agentic_soc.agent.graph import graph

def main():
   alert_id = sys.argv[1] if len(sys.argv) > 1 else None

   result = graph.invoke({"alert_id": alert_id})

   print("Investigation Result:")
   pprint(result, width=100, sort_dicts=False)

   output_dir = Path(__file__).resolve().parents[2] / "outputs"
   output_dir.mkdir(exist_ok=True)

   output_file = output_dir / "agentic_soc_last_run.json"

   output = {
      **result,
      "messages": messages_to_dict(result["messages"]),
   }

   with open(output_file, "w", encoding="utf-8") as f:
      json.dump(output, f, indent=2)

   print(f"Full run saved to: {output_file}") 

if __name__ == "__main__":
   main()
