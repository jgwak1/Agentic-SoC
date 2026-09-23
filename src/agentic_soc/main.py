import sys
from pprint import pformat

from agentic_soc.agent.graph import graph


def main():
   alert_id = sys.argv[1] if len(sys.argv) > 1 else None

   result = graph.invoke({"alert_id": alert_id})

   print("Investigation Result:")
   print(result)

   output_file = "/tmp/agentic_soc_last_run.txt"

   with open(output_file, "w") as f:
      f.write(pformat(result, width=120))

   print(f"Full run saved to: {output_file}")



if __name__ == "__main__":
   main()