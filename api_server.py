# api_server.py
import os
import json
import uuid
import logging
import asyncio
from datetime import datetime
from pydantic import BaseModel
from typing import Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header

# make sure repo root is importable if needed
repo_root = os.path.dirname(__file__)
if repo_root not in os.sys.path:
    os.sys.path.insert(0, repo_root)

# import your pipeline (adjust import path if different)
from eval_pipeline.eval_1_3 import pipeline

# load environment (dotenv)
from dotenv import load_dotenv
load_dotenv(os.path.join(repo_root, ".env"))

API_KEY = os.getenv("EVAL_API_KEY", "change-me")
INPUT_DIR = os.getenv("EVAL_INPUT_DIR", "/home/azureuser/eval_data/inputs")
OUTPUT_DIR = os.getenv("EVAL_OUTPUT_DIR", "/home/azureuser/eval_data/outputs")
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adcopy-eval-api")

app = FastAPI(title="Ad Copy Eval API")

class EvalRequest(BaseModel):
    brand: str
    date: str         # e.g. "2025-09-12" (string)
    data: List[Any]   # list of trends (same as top_k_trends)

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/run-eval")
async def run_eval(req: EvalRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    # Basic API key auth
    if API_KEY == "change-me":
        logger.warning("EVAL_API_KEY is the default; set a secure value in .env")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # create unique filenames
    job_id = uuid.uuid4().hex[:8]
    input_filename = f"input_{req.brand}_{req.date}_{job_id}.json"
    output_filename = f"output_{req.brand}_{req.date}_{job_id}.csv"
    input_path = os.path.join(INPUT_DIR, input_filename)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # Save the posted data as the same structure your pipeline expects
    payload = {"top_k_trends": req.data}
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Received job %s: brand=%s date=%s input=%s", job_id, req.brand, req.date, input_path)

    # schedule background work
    background_tasks.add_task(_run_pipeline_background, input_path, output_path, req.brand, job_id)

    return {"status": "accepted", "job_id": job_id, "input_file": input_path, "output_file": output_path}

async def _run_pipeline_background(input_path: str, output_path: str, brand: str, job_id: str):
    """Run the blocking pipeline in a thread to avoid blocking the FastAPI event loop."""
    try:
        logger.info("Starting pipeline for job %s", job_id)
        result = await asyncio.to_thread(pipeline, input_path, output_path, brand)
        # write a small status file
        status_path = output_path + ".status.json"
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump({"job_id": job_id, "result": result, "completed_at": datetime.utcnow().isoformat()}, f, indent=2)
        logger.info("Pipeline finished for job %s, result saved to %s", job_id, output_path)
    except Exception as e:
        logger.exception("Pipeline failed for job %s: %s", job_id, str(e))
        fail_path = output_path + ".failed.json"
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump({"job_id": job_id, "error": str(e), "time": datetime.utcnow().isoformat()}, f, indent=2)
