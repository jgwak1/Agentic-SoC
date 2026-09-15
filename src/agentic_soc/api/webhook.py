import json
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

# Elastic
#     ↓ HTTP POST
# Uvicorn
#     ↓
# FastAPI
#     ↓ route matching
# /webhooks/elastic
#     ↓
# receive_elastic_alert()
#     ↓
# later: fetch alert → start LangGraph investigator


ROOT = Path(__file__).resolve().parents[3]
CONFIG_FILE = ROOT / "config" / "elastic.config.json"

with open(CONFIG_FILE, encoding="utf-8") as f:
     config = json.load(f)

WEBHOOK_SECRET = config["webhook_secret"]

app = FastAPI(title = "Agentic SOC") # create Agentic SOC FastAPI webapp instance

class ElasticAlertWebhook(BaseModel):
   alert_id : str

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/webhooks/elastic", status_code=status.HTTP_202_ACCEPTED)
async def receive_elastic_alert( payload : ElasticAlertWebhook,
                                 x_agentic_soc_token: str = Header(...) ):

   if not secrets.compare_digest(x_agentic_soc_token, WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token",
        )

   print(f"Received Elastic alert: {payload.alert_id}")

    # Later:
    # 1. Fetch the full alert from Elastic.
    # 2. Start the LangGraph investigator.
    # 3. Persist the investigation result.


   return {
       "status": "accepted",
       "alert_id": payload.alert_id,
   }

