from openai import OpenAI
import anthropic
import json
import sys
import os
import pandas as pd
import re
from prompts.prompts import instruction_prompt_1_3
from tests.functions import evaluate,get_company_context
from datetime import datetime


def load_suggestion_data(file_path: str):
    """Load Ad copy analysis json and return list of top_k_trends as dicts."""
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("top_k_trends", [])


def parse_scores_for_single_output(llm_output: str):
    """
    Parse dimension scores and return all scores for comprehensive logging.
    Returns detailed breakdown for CSV + all individual scores for Langfuse.
    """
    dimensions = {
        "strategic": 0.2,
        "non_obvious": 0.1,
        "specificity": 0.2,
        "impactful": 0.2,
        "clarity": 0.1,
        "actionable": 0.2
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
        with open("broken_llm_output.json", "w", encoding="utf-8") as f:
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
    normalized_pct = (weighted_total / 3.0) * 100

 
    summary_lines = []
    for dim, weight in dimensions.items():
        summary_lines.append(
            f"{dim}: {parsed_scores[dim]} × {weight} = {weighted_scores[dim]:.2f}"
        )
    summary_lines.append(f"\nWeighted Total: {weighted_total:.2f}")
    summary_lines.append(f"Average Score: {avg_score:.2f} out of 3.0")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")

    return {
        "normalized_score": normalized_pct,
        "detailed_summary": "\n".join(summary_lines),
        "raw_scores": parsed_scores,
        "weighted_total": weighted_total,
        "avg_score": avg_score
    }

def evaluate_single_trend(datapoint, full_instruction_prompt, trend_index, total_trends, brand):
    """
    Complete evaluation flow for a single trend with comprehensive Langfuse scoring:
    1. Log trace with metadata
    2. Run evaluation 
    3. Log ALL individual dimension scores + aggregate scores
    """
    
    trend_name = datapoint['trend']
    industry_score = datapoint.get("industry_score", "N/A")
    
    print(f"=== Evaluating trend {trend_index}/{total_trends}: {trend_name} ===")
    
    
    # Step 2: Run the actual evaluation process (this creates sub-traces)
    try:
        # Get LLM evaluation (this will be traced as sub-process)
        llm_output = evaluate(datapoint, full_instruction_prompt)
        
        # Parse scores (this will be traced as sub-process) 
        score_results = parse_scores_for_single_output(llm_output)
        
        normalized_score = score_results["normalized_score"]
        
        print(f" Trend '{trend_name}' scored: {normalized_score:.1f}%")
        
        return {
            "trend": trend_name,
            "industry_score": industry_score,
            "normalized_score": normalized_score,
            "analysis": json.dumps(datapoint.get("analysis", {}), indent=2, ensure_ascii=False),
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success"
        }
        
    except Exception as e:
        # Log failed evaluation with zero scores for all dimensions
        print(f" Error evaluating trend '{trend_name}': {e}")
        return {
            "trend": trend_name,
            "industry_score": industry_score,
            "normalized_score": 0.0,
            "analysis": "EVALUATION FAILED",
            "score_summary": f"Error: {str(e)}",
            "reasoning": "EVALUATION FAILED",
            "status": "failed"
        }

def pipeline(input_path, output_path, brand):
    """
    Main pipeline with comprehensive Langfuse scoring.
    Each trend gets its own trace with all dimension scores + aggregate scores.
    Pipeline gets its own aggregate metrics.
    """
    
    print(f"\n Starting Ad Copy Evaluation Pipeline for {brand}")
    
    
    try:
        print(f" Fetching company context for {brand}...")
        company_context = get_company_context(brand)
        full_instruction_prompt = instruction_prompt_1_3 + f"\n\nAdditional context about Brand:\n{company_context}"
        
        print(f" Loading trends from {os.path.basename(input_path)}...")
        suggestion_data = load_suggestion_data(input_path)
        total_trends = len(suggestion_data)
        
        print(f" Found {total_trends} trends to evaluate")
        
        results = []
        successful_evaluations = 0

        for i, datapoint in enumerate(suggestion_data, 1):
            result = evaluate_single_trend(
                datapoint, 
                full_instruction_prompt, 
                i, 
                total_trends,
                brand
            )
            results.append(result)
            
            if result["status"] == "success":
                successful_evaluations += 1
        
        print(f" Saving results to {os.path.basename(output_path)}...")
        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding="utf-8")
        
        success_rate = (successful_evaluations / total_trends) * 100 if total_trends > 0 else 0
        avg_pipeline_score = df[df['status'] == 'success']['normalized_score'].mean() if successful_evaluations > 0 else 0
        
        print(f"\n Pipeline completed successfully!")
        print(f" Results: {successful_evaluations}/{total_trends} trends evaluated ({success_rate:.1f}% success)")
        print(f" Average score: {avg_pipeline_score:.1f}%" if successful_evaluations > 0 else "No successful evaluations")
        print(f" Output saved to: {output_path}")
        
        return {
            "status": "success",
            "total_trends": total_trends,
            "successful": successful_evaluations,
            "output_path": output_path,
            "success_rate": success_rate
        }
        
    except Exception as e:
        print(f" Pipeline failed: {e}")
        raise e