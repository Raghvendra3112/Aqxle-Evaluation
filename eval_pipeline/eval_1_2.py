import json
import os
import re
from datetime import datetime
from typing import Dict, Any

import pandas as pd
from langfuse import observe, get_client

from prompts.prompts import instruction_prompt_1_2
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context

langfuse = get_client()


@observe(as_type="retriever", name="Load Keyword Data")
def load_suggestion_data(file_path: str):
    """Load keyword JSON (with search_volume_analysis + trend_analysis)."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@observe(as_type="span", name="Parse Evaluation Scores")
def parse_scores_for_single_output(llm_output: str):
    """
    Parse dimension scores and return all scores for logging.
    Dimensions: strategic, non_obvious, specificity, actionable, impactful.
    """
    dimensions = {
        "strategic": 0.2,
        "non_obvious": 0.15,
        "specificity": 0.15,
        "actionable": 0.3,
        "impactful": 0.2,
    }

    parsed_scores = {}
    weighted_scores = {}

    llm_output = llm_output.strip()
    if llm_output.startswith("```"):
        llm_output = re.sub(r"^```(?:json)?", "", llm_output, flags=re.IGNORECASE).strip()
        llm_output = re.sub(r"```$", "", llm_output).strip()

    try:
        output_dict = json.loads(llm_output)
    except json.JSONDecodeError as e:
        with open("broken_llm_output_1_2.json", "w", encoding="utf-8") as f:
            f.write(llm_output)
        raise ValueError(f"Invalid JSON from LLM: {e}")

    for dim, weight in dimensions.items():
        if dim in output_dict and "score" in output_dict[dim]:
            parsed_scores[dim] = int(output_dict[dim]["score"])
            weighted_scores[dim] = parsed_scores[dim] * weight
        else:
            parsed_scores[dim] = None
            weighted_scores[dim] = 0.0

    weighted_total = sum(weighted_scores.values())
    avg_score = weighted_total / len(dimensions)
    normalized_pct = (weighted_total / 3.0) * 100  # same scale as 1_3

    summary_lines = []
    for dim, weight in dimensions.items():
        summary_lines.append(f"{dim}: {parsed_scores[dim]} × {weight} = {weighted_scores[dim]:.2f}")
    summary_lines.append(f"\nWeighted Total: {weighted_total:.2f}")
    summary_lines.append(f"Average Score: {avg_score:.2f} out of 3.0")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")

    return {
        "normalized_score": normalized_pct,
        "detailed_summary": "\n".join(summary_lines),
        "raw_scores": parsed_scores,
        "weighted_total": weighted_total,
        "avg_score": avg_score,
    }


@observe(as_type="chain", name="Evaluate Branded Summary")
def evaluate_branded_summary(branded_data: Dict[str, Any], full_instruction_prompt: str, brand: str):
    """Evaluate the top_branded summary + keywords context."""
    summary = branded_data.get("summary", "")
    keywords = branded_data.get("keywords", [])

    langfuse.update_current_trace(
        name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={"brand": brand, "evaluation_type": "branded_summary"},
        user_id="raghvendra",
    )

    try:
        datapoint = {"summary": summary, "keywords": keywords}
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_results = parse_scores_for_single_output(llm_output)

        trace_id = langfuse.get_current_trace_id()
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"branded_{dim}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )

        return {
            "type": "branded_summary",
            "summary": summary,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
    except Exception as e:
        return {"type": "branded_summary", "status": "failed", "error": str(e)}


@observe(as_type="chain", name="Evaluate Non-Branded Summary")
def evaluate_nonbranded_summary(nonbranded_data: Dict[str, Any], full_instruction_prompt: str, brand: str):
    """Evaluate the top_non_branded summary + keywords context."""
    summary = nonbranded_data.get("summary", "")
    keywords = nonbranded_data.get("keywords", [])

    langfuse.update_current_trace(
        name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={"brand": brand, "evaluation_type": "nonbranded_summary"},
        user_id="raghvendra",
    )

    try:
        datapoint = {"summary": summary, "keywords": keywords}
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_results = parse_scores_for_single_output(llm_output)

        trace_id = langfuse.get_current_trace_id()
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"nonbranded_{dim}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )

        return {
            "type": "nonbranded_summary",
            "summary": summary,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
    except Exception as e:
        return {"type": "nonbranded_summary", "status": "failed", "error": str(e)}


@observe(as_type="chain", name="Evaluate Single Trend (1.2)")
def evaluate_single_trend(datapoint: Dict[str, Any], full_instruction_prompt: str, trend_index: int, total_trends: int, brand: str):
    """Evaluate a single trend analysis datapoint (same naming as 1_3)."""
    trend_text = datapoint.get("trend", "N/A")

    langfuse.update_current_trace(
        name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={"brand": brand, "evaluation_type": "trend_analysis", "trend_index": trend_index},
        user_id="raghvendra",
    )

    try:
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_results = parse_scores_for_single_output(llm_output)

        trace_id = langfuse.get_current_trace_id()
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"{dim}_score",  # same as 1_3
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )

        return {
            "type": "trend_analysis",
            "trend": trend_text,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
    except Exception as e:
        return {"type": "trend_analysis", "trend": trend_text, "status": "failed", "error": str(e)}


@observe(as_type="chain", name="Keyword Evaluation Pipeline 1.2")
def pipeline(input_path: str, output_path: str, brand: str):
    """Main pipeline for keyword analysis evaluation (1.2)."""
    data = load_suggestion_data(input_path)
    full_prompt = instruction_prompt_1_2 + "\n\n" + get_company_context(brand)

    results = []

    langfuse.update_current_trace(
        name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={"brand": brand, "evaluation_type": "nonbranded_summary"},
        tags=["pipeline", "keyword-analysis", brand.lower()],
        user_id="raghvendra",
    )
    # Branded
    branded = data.get("search_volume_analysis", {}).get("top_branded", {})
    if branded:
        results.append(evaluate_branded_summary(branded, full_prompt, brand))

    # Non-branded
    nonbranded = data.get("search_volume_analysis", {}).get("top_non_branded", {})
    if nonbranded:
        results.append(evaluate_nonbranded_summary(nonbranded, full_prompt, brand))

    # Trend Analysis
    trends = data.get("trend_analysis", [])
    for idx, trend in enumerate(trends, 1):
        results.append(evaluate_single_trend(trend, full_prompt, idx, len(trends), brand))

    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)

    return results
