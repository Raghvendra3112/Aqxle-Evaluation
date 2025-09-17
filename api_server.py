# api_server.py
import os
import json
import uuid
import logging
import asyncio
from datetime import datetime
from pydantic import BaseModel
from typing import Any, List, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header

repo_root = os.path.dirname(__file__)
if repo_root not in os.sys.path:
    os.sys.path.insert(0, repo_root)

# import pipelines
from eval_pipeline.eval_1_3 import pipeline as pipeline_1_3
from eval_pipeline.eval_1_2 import pipeline as pipeline_1_2

from dotenv import load_dotenv
load_dotenv(os.path.join(repo_root, ".env"))

API_KEY = os.getenv("EVAL_API_KEY", "change-me")
INPUT_DIR = os.getenv("EVAL_INPUT_DIR", "/home/azureuser/eval_data/inputs")
OUTPUT_DIR = os.getenv("EVAL_OUTPUT_DIR", "/home/azureuser/eval_data/outputs")
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Aqxle-eval-api")

app = FastAPI(title="Aqxle Eval API")


# ---------- Models ----------

class AdCopyEvalRequest(BaseModel):
    brand: str
    date: str
    data: List[Any]  # same as top_k_trends


class KeywordEvalRequest(BaseModel):
    brand: str
    date: str
    data: Dict[str, Any]  # search_volume_analysis + trend_analysis


# ---------- Routes ----------

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/run-ad-copy-eval")
async def run_ad_copy_eval(req: AdCopyEvalRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    if API_KEY == "change-me":
        logger.warning("EVAL_API_KEY is the default; set a secure value in .env")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    job_id = uuid.uuid4().hex[:8]
    input_filename = f"adcopy_input_{req.brand}_{req.date}_{job_id}.json"
    output_filename = f"adcopy_output_{req.brand}_{req.date}_{job_id}.csv"
    input_path = os.path.join(INPUT_DIR, input_filename)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    payload = {"top_k_trends": req.data}
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Received Ad Copy job %s: brand=%s date=%s input=%s", job_id, req.brand, req.date, input_path)
    background_tasks.add_task(_run_pipeline_background, pipeline_1_3, input_path, output_path, req.brand, job_id)

    return {"status": "accepted", "job_id": job_id, "input_file": input_path, "output_file": output_path}


@app.post("/run-keyword-eval")
async def run_keyword_eval(req: KeywordEvalRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    if API_KEY == "change-me":
        logger.warning("EVAL_API_KEY is the default; set a secure value in .env")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    job_id = uuid.uuid4().hex[:8]
    input_filename = f"keyword_input_{req.brand}_{req.date}_{job_id}.json"
    output_filename = f"keyword_output_{req.brand}_{req.date}_{job_id}.csv"
    input_path = os.path.join(INPUT_DIR, input_filename)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    payload = req.data  # already has search_volume_analysis + trend_analysis
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Received Keyword job %s: brand=%s date=%s input=%s", job_id, req.brand, req.date, input_path)
    background_tasks.add_task(_run_pipeline_background, pipeline_1_2, input_path, output_path, req.brand, job_id)

    return {"status": "accepted", "job_id": job_id, "input_file": input_path, "output_file": output_path}


# ---------- Background runner ----------

async def _run_pipeline_background(pipeline_func, input_path: str, output_path: str, brand: str, job_id: str):
    try:
        logger.info("Starting pipeline for job %s", job_id)
        result = await asyncio.to_thread(pipeline_func, input_path, output_path, brand)
        status_path = output_path + ".status.json"
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(
                {"job_id": job_id, "result": result, "completed_at": datetime.utcnow().isoformat()},
                f,
                indent=2,
            )
        logger.info("Pipeline finished for job %s, result saved to %s", job_id, output_path)
    except Exception as e:
        logger.exception("Pipeline failed for job %s: %s", job_id, str(e))
        fail_path = output_path + ".failed.json"
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump({"job_id": job_id, "error": str(e), "time": datetime.utcnow().isoformat()}, f, indent=2)
