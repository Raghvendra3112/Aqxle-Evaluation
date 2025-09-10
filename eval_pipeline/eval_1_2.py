""" INPUT FORMAT -- 

OUTPATH PATH - must be csv

"""

from openai import OpenAI
import anthropic
import json
import sys
import os
import pandas as pd
import re
from typing import List, Dict, Any
from langfuse import observe, get_client
from datetime import datetime

from prompts.prompts import instruction_prompt_1_2
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context

langfuse = get_client()


@observe(as_type="retriever", name="Load Suggestion Data")
def load_suggestion_data(file_path: str) -> List[Dict[str, any]]:
    """
    Load JSON file containing keyword category, actionable news, and insights.
    Extracts only:
      - Keyword Category
      - Actionable News
      - Insight
    Returns a list of dicts:
    [
      {
        "Keyword Category": ...,
        "Actionable News": [...],
        "Insight": [...]
      },
      ...
    ]
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle case where JSON is a single dict instead of a list of dicts
    if isinstance(data, dict):
        data = [data]

    extracted = []
    for entry in data:
        if not all(k in entry for k in ("Keyword Category", "Actionable News", "Insight")):
            raise ValueError("Each entry must contain 'Keyword Category', 'Actionable News', and 'Insight'")

        extracted.append({
            "Keyword Category": entry["Keyword Category"],
            "Actionable News": entry["Actionable News"],
            "Insight": entry["Insight"],
        })

    return extracted


@observe(as_type="span", name="Parse Evaluation Scores")
def parse_scores_for_single_output(llm_output: str):
    """
    Parse dimension scores (1-3 scale) and compute weighted + normalized scores.
    Returns detailed breakdown for CSV + all individual scores for Langfuse.
    """
    dimensions = {
        "Strategic": 0.2,
        "Non_obvious": 0.15,
        "Specificity": 0.15,
        "Actionable": 0.3,
        "Impactful": 0.2
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

    # Calculate weighted total and normalized percentage
    weighted_total = sum(weighted_scores.values())
    avg_score = weighted_total / len(dimensions)
    # For 1.2: max possible weighted total is 0.6 (3 * 0.2) when all dimensions score 3
    max_weighted_total = 0.6  # 3 * (0.2 + 0.15 + 0.15 + 0.3 + 0.2) = 3 * 1.0 = 3.0, but avg is 0.6
    normalized_pct = (avg_score / 0.6) * 100

    # Create detailed summary
    summary_lines = []
    for dim, weight in dimensions.items():
        summary_lines.append(
            f"{dim}: {parsed_scores[dim]} × {weight} = {weighted_scores[dim]:.2f}"
        )
    summary_lines.append(f"\nWeighted Total: {weighted_total:.2f}")
    summary_lines.append(f"Average Score: {avg_score:.2f} out of 0.6")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")

    return {
        "normalized_score": normalized_pct,
        "detailed_summary": "\n".join(summary_lines),
        "raw_scores": parsed_scores,
        "weighted_total": weighted_total,
        "avg_score": avg_score
    }


@observe(as_type="chain", name="Single Datapoint Evaluation")
def evaluate_single_datapoint(datapoint, full_instruction_prompt, datapoint_index, total_datapoints, brand):
    """
    Complete evaluation flow for a single datapoint with comprehensive Langfuse scoring:
    1. Log trace with metadata
    2. Run evaluation 
    3. Log ALL individual dimension scores + aggregate scores
    """
    
    keyword_category = datapoint.get('Keyword Category', 'N/A')
    
    print(f"=== Evaluating datapoint {datapoint_index}/{total_datapoints}: {keyword_category} ===")
    
    # Step 1: Update trace with comprehensive metadata
    langfuse.update_current_trace(
       name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={
            "brand": brand,
            "keyword_category": keyword_category,
            "datapoint_index": datapoint_index,
            "total_datapoints": total_datapoints,
            "evaluation_version": "1.2",
            "model_primary": "claude-opus-4-1",
            "model_context": "gpt-4.1"
        },
        user_id=f"raghvendra"
    )
    
    # Step 2: Run the actual evaluation process (this creates sub-traces)
    try:
        # Get LLM evaluation (this will be traced as sub-process)
        llm_output = evaluate(datapoint, full_instruction_prompt)
        
        # Parse scores (this will be traced as sub-process) 
        score_results = parse_scores_for_single_output(llm_output)
        
        normalized_score = score_results["normalized_score"]
        
        # Step 3: Log ALL scores to Langfuse
        trace_id = langfuse.get_current_trace_id()
        
        # Log individual dimension scores (1-3 scale)
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"{dim.lower()}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                    comment=f"{dim} evaluation score (1-3 scale) for category: {keyword_category}"
                )
        
        # Log weighted total score
        langfuse.create_score(
            name="weighted_total_score",
            value=score_results["weighted_total"],
            trace_id=trace_id,
            data_type="NUMERIC", 
            comment=f"Weighted total score for {keyword_category} (Brand: {brand}). Sum of all dimension scores × weights."
        )
        
        # Log average score
        langfuse.create_score(
            name="average_score",
            value=score_results["avg_score"],
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Average weighted score for {keyword_category} (Brand: {brand}). Weighted total ÷ number of dimensions."
        )
        
        # Log final normalized percentage score
        langfuse.create_score(
            name="normalized_percentage",
            value=normalized_score,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Final normalized percentage score (0-100%) for {keyword_category} (Brand: {brand}). Primary evaluation metric."
        )
        
        print(f" Category '{keyword_category}' scored: {normalized_score:.1f}%")
        
        return {
            "keyword_category": keyword_category,
            "news": datapoint["Actionable News"],
            "insight": datapoint["Insight"],
            "normalized_score": normalized_score,
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success"
        }
        
    except Exception as e:
        # Log failed evaluation with zero scores for all dimensions
        print(f" Error evaluating category '{keyword_category}': {e}")
        
        trace_id = langfuse.get_current_trace_id()
        
        # Log zero scores for all dimensions
        dimensions = ["strategic", "nonobvious", "specificity", "actionable", "impactful"]
        for dim in dimensions:
            langfuse.create_score(
                name=f"{dim}_score",
                value=0,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=f"Failed evaluation - {dim} score set to 0 for {keyword_category}. Error: {str(e)}"
            )
        
        # Log zero aggregate scores
        langfuse.create_score(
            name="weighted_total_score",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - weighted total set to 0 for {keyword_category}. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="average_score", 
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - average score set to 0 for {keyword_category}. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="normalized_percentage",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - normalized percentage set to 0 for {keyword_category}. Error: {str(e)}"
        )
        
        return {
            "keyword_category": keyword_category,
            "news": datapoint["Actionable News"],
            "insight": datapoint["Insight"],
            "normalized_score": 0.0,
            "score_summary": f"Error: {str(e)}",
            "reasoning": "EVALUATION FAILED",
            "status": "failed"
        }


@observe(as_type="chain", name="Insights Evaluation Pipeline")
def pipeline(input, output, brand):
    """
    Main pipeline with comprehensive Langfuse scoring.
    Each datapoint gets its own trace with all dimension scores + aggregate scores.
    Pipeline gets its own aggregate metrics.
    """
    
    input_path = input
    output_path = output
    
    print(f"\n Starting Insights Evaluation Pipeline for {brand}")
    
    langfuse.update_current_trace(
        name=f"{brand} Insights Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={
            "brand": brand,
            "input_file": os.path.basename(input_path),
            "output_file": os.path.basename(output_path),
            "pipeline_version": "1.2",
            "evaluation_dimensions": ["Strategic", "Nonobvious", "Specificity", "Actionable", "Impactful"],
            "scoring_method": "weighted_normalized"
        },
        tags=["pipeline", "keyword-analysis", brand.lower()],
        user_id=f"raghvendra"
    )
    
    try:
        print(f" Fetching company context for {brand}...")
        company_context = get_company_context(brand)
        full_instruction_prompt = instruction_prompt_1_2 + f"\n\nAdditional context about Brand:\n{company_context}"
      
        print(f" Loading datapoints from {os.path.basename(input_path)}...")
        suggestion_data = load_suggestion_data(input_path)
        total_datapoints = len(suggestion_data)
        
        print(f" Found {total_datapoints} datapoints to evaluate")
        
        results = []
        successful_evaluations = 0

        for i, datapoint in enumerate(suggestion_data, 1):
            result = evaluate_single_datapoint(
                datapoint, 
                full_instruction_prompt, 
                i, 
                total_datapoints,
                brand
            )
            results.append(result)
            
            if result["status"] == "success":
                successful_evaluations += 1
        
        print(f" Saving results to {os.path.basename(output_path)}...")
        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding="utf-8")
        
        success_rate = (successful_evaluations / total_datapoints) * 100 if total_datapoints > 0 else 0
        avg_pipeline_score = df[df['status'] == 'success']['normalized_score'].mean() if successful_evaluations > 0 else 0
        
        print(f"\n Pipeline completed successfully!")
        print(f" Results: {successful_evaluations}/{total_datapoints} datapoints evaluated ({success_rate:.1f}% success)")
        print(f" Average score: {avg_pipeline_score:.1f}%" if successful_evaluations > 0 else "No successful evaluations")
        print(f" Output saved to: {output_path}")
        print(f" Check Langfuse dashboard for comprehensive scoring data!")
        
        return {
            "status": "success",
            "total_datapoints": total_datapoints,
            "successful": successful_evaluations,
            "output_path": output_path,
            "success_rate": success_rate
        }
        
    except Exception as e:
        print(f" Pipeline failed: {e}")
        raise e
    finally:
        langfuse.flush()