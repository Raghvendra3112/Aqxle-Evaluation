""" 
Langfuse Evaluation System with Single Normalized Score Output
Optimized for Free Plan (1 score per trace)
"""

from openai import OpenAI
import anthropic
import json
import sys
import os
import pandas as pd
import re
from langfuse import observe,get_client
from prompts.prompts import instruction_prompt_1_3
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context

# Initialize Langfuse client
langfuse = get_client()

@observe(name="Load Trend Data")
def load_suggestion_data(file_path: str):
    """Load Ad copy analysis json and return list of top_k_trends as dicts."""
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("top_k_trends", [])


@observe(name="Parse Evaluation Scores")
def parse_scores_for_single_output(llm_output: str):
    """
    Parse dimension scores and return ONLY normalized score for Langfuse.
    Returns detailed breakdown for CSV + single normalized score for Langfuse.
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

    # Clean LLM output
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

    # Extract and calculate scores
    for dim, weight in dimensions.items():
        if dim in output_dict and "score" in output_dict[dim]:
            parsed_scores[dim] = int(output_dict[dim]["score"])
            weighted_scores[dim] = parsed_scores[dim] * weight
        else:
            parsed_scores[dim] = None
            weighted_scores[dim] = 0.0

    # Calculate final metrics
    weighted_total = sum(weighted_scores.values())
    avg_score = weighted_total / len(dimensions)
    normalized_pct = (weighted_total / 3.0) * 100  # This is our single output score

    # Create detailed summary for CSV
    summary_lines = []
    for dim, weight in dimensions.items():
        summary_lines.append(
            f"{dim}: {parsed_scores[dim]} × {weight} = {weighted_scores[dim]:.2f}"
        )
    summary_lines.append(f"\nWeighted Total: {weighted_total:.2f}")
    summary_lines.append(f"Average Score: {avg_score:.2f} out of 3.0")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")

    return {
        "normalized_score": normalized_pct,  # This goes to Langfuse
        "detailed_summary": "\n".join(summary_lines),  # This goes to CSV
        "raw_scores": parsed_scores,
        "weighted_total": weighted_total,
        "avg_score": avg_score
    }


@observe(name="Single Trend Evaluation")
def evaluate_single_trend(datapoint, full_instruction_prompt, trend_index, total_trends, brand):
    """
    Complete evaluation flow for a single trend with proper Langfuse structure:
    1. Log trace with metadata
    2. Run evaluation 
    3. Log single normalized score
    """
    
    trend_name = datapoint['trend']
    industry_score = datapoint.get("industry_score", "N/A")
    
    print(f"=== Evaluating trend {trend_index}/{total_trends}: {trend_name} ===")
    
    # Step 1: Update trace with comprehensive metadata
    langfuse.update_current_trace(
        name=f"Ad Copy Evaluation: {trend_name}",
        metadata={
            "brand": brand,
            "trend_name": trend_name,
            "trend_index": trend_index,
            "total_trends": total_trends,
            "industry_score": industry_score,
            "evaluation_version": "1.3",
            "model_primary": "claude-opus-4-1",
            "model_context": "gpt-4.1"
        },
        tags=["ad-copy-evaluation", brand.lower(), "v1.3"],
        user_id=f"eval-system-{brand.lower()}"
    )
    
    # Step 2: Run the actual evaluation process (this creates sub-traces)
    try:
        # Get LLM evaluation (this will be traced as sub-process)
        llm_output = evaluate(datapoint, full_instruction_prompt)
        
        # Parse scores (this will be traced as sub-process) 
        score_results = parse_scores_for_single_output(llm_output)
        
        normalized_score = score_results["normalized_score"]
        
        # Step 3: Log the SINGLE score as LLM-as-Judge result
        trace_id = langfuse.get_current_trace_id()
        
        langfuse.create_score(
          name="evaluation_score",
          value=normalized_score,
          trace_id=trace_id,
          data_type="NUMERIC",
          comment="Normalised score"
        )
        
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
        # Log failed evaluation
        print(f" Error evaluating trend '{trend_name}': {e}")
        
        trace_id = langfuse.get_current_trace_id()
        langfuse.create_score(
          name="evaluation_score",
          value=0.0,
          trace_id=trace_id,
          data_type="NUMERIC",
          comment="Evaluation failed"
      )
        
        return {
            "trend": trend_name,
            "industry_score": industry_score,
            "normalized_score": 0.0,
            "analysis": "EVALUATION FAILED",
            "score_summary": f"Error: {str(e)}",
            "reasoning": "EVALUATION FAILED",
            "status": "failed"
        }


@observe(name="Ad Copy Evaluation Pipeline")
def pipeline(input_path, output_path, brand):
    """
    Main pipeline with proper Langfuse session structure.
    Each trend gets its own trace with one normalized score.
    """
    
    print(f"\n Starting Ad Copy Evaluation Pipeline for {brand}")
    
    # Pipeline-level metadata
    langfuse.update_current_trace(
        name=f"Ad Copy Pipeline - {brand}",
        metadata={
            "brand": brand,
            "input_file": os.path.basename(input_path),
            "output_file": os.path.basename(output_path),
            "pipeline_version": "1.3",
            "evaluation_dimensions": ["strategic", "non_obvious", "specificity", "impactful", "clarity", "actionable"],
            "scoring_method": "weighted_normalized"
        },
        tags=["pipeline", "ad-copy-analysis", brand.lower()],
        user_id=f"pipeline-{brand.lower()}"
    )
    
    try:
        # Step 1: Get company context (traced automatically)
        print(f" Fetching company context for {brand}...")
        company_context = get_company_context(brand)
        full_instruction_prompt = instruction_prompt_1_3 + f"\n\nAdditional context about Brand:\n{company_context}"
        
        # Step 2: Load evaluation data (traced automatically)
        print(f" Loading trends from {os.path.basename(input_path)}...")
        suggestion_data = load_suggestion_data(input_path)
        total_trends = len(suggestion_data)
        
        print(f" Found {total_trends} trends to evaluate")
        
        results = []
        successful_evaluations = 0

        # Step 3: Process each trend (each creates separate trace with score)
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
        
        # Step 4: Save results to CSV
        print(f" Saving results to {os.path.basename(output_path)}...")
        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding="utf-8")
        
        # Step 5: Log pipeline summary (no additional score, just metadata)
        success_rate = (successful_evaluations / total_trends) * 100 if total_trends > 0 else 0
        
        #langfuse.update_current_trace(
        #    metadata={
        #        **langfuse.get_current_trace().metadata,
        #        "results": {
        #            "total_trends": total_trends,
        #            "successful_evaluations": successful_evaluations, 
        #            "success_rate_pct": success_rate,
        #            "average_score": df[df['status'] == 'success']['normalized_score'].mean() if successful_evaluations > 0 else 0
        #        }
        #    }
        #)
        
        print(f"\n Pipeline completed successfully!")
        print(f" Results: {successful_evaluations}/{total_trends} trends evaluated ({success_rate:.1f}% success)")
        print(f" Average score: {df[df['status'] == 'success']['normalized_score'].mean():.1f}%" if successful_evaluations > 0 else "No successful evaluations")
        print(f" Output saved to: {output_path}")
        print(f" Check Langfuse dashboard for individual trend scores!")
        
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
    finally:
        # Flush Langfuse data
        langfuse.flush()