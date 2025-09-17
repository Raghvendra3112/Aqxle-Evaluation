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
    Parse dimension scores and return all scores for comprehensive logging.
    Returns detailed breakdown for CSV + all individual scores for Langfuse.
    """
    dimensions = {
        "strategic": 0.2,
        "non_obvious": 0.15,
        "specificity": 0.15,
        "impactful": 0.2,
        "actionable": 0.3
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


@observe(as_type="chain", name="Branded Evaluation")
def evaluate_branded_summary(branded_data: Dict[str, Any], full_instruction_prompt: str, brand: str, trace_id: str):
    """Evaluate the top_branded summary + keywords context."""
    summary = branded_data.get("summary", "")
    keywords = branded_data.get("keywords", [])
    langfuse.update_current_trace(
       name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={
            "brand": brand,
            "evaluation_version": "1.2",
            "model_primary": "claude-opus-4-1",
            "model_context": "gpt-4.1"
        },
        user_id=f"raghvendra"
    )
    try:
        datapoint = {"summary": summary, "keywords": keywords}
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_results = parse_scores_for_single_output(llm_output)
        normalized_score = score_results["normalized_score"]

        trace_id = langfuse.get_current_trace_id()

        # Attach all scores to the same top-level trace
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"branded_{dim}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )

        # Log weighted total score
        langfuse.create_score(
            name="branded_weighted_total_score",
            value=score_results["weighted_total"],
            trace_id=trace_id,
            data_type="NUMERIC", 
            comment=f"Weighted total score for Branded (Brand: {brand}). Sum of all dimension scores × weights."
        )
        
        # Log average score
        langfuse.create_score(
            name="branded_average_score",
            value=score_results["avg_score"],
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Average weighted score for Branded (Brand: {brand}). Weighted total ÷ number of dimensions."
        )
        
        # Log final normalized percentage score
        langfuse.create_score(
            name="branded_normalized_percentage",
            value=normalized_score,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Final normalized percentage score (0-100%) for Branded (Brand: {brand}). Primary evaluation metric."
        )
        
        print(f" Branded Keywords summary scored: {normalized_score:.1f}%")
        
        return {
            "type": "branded_summary",
            "summary": summary,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
        
    except Exception as e:
        # Log failed evaluation with zero scores for all dimensions
        print(f" Error evaluating trend Branded Summary: {e}")
        
        trace_id = langfuse.get_current_trace_id()
        
        # Log zero scores for all dimensions
        dimensions = ["strategic", "non_obvious", "specificity", "impactful", "actionable"]
        for dim in dimensions:
            langfuse.create_score(
                name=f"barnded_{dim}_score",
                value=0,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=f"Failed evaluation - {dim} score set to 0 for Branded Summary. Error: {str(e)}"
            )
        
        # Log zero aggregate scores
        langfuse.create_score(
            name="branded_weighted_total_score",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - weighted total set to 0 for Branded Summary. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="branded_average_score", 
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - average score set to 0 for Branded Summary. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="branded_normalized_percentage",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - normalized percentage set to 0 for Branded Summary. Error: {str(e)}"
        )
        
        return {
            "type": "branded_summary",
            "summary": summary,
            "normalized_score": 0.0,
            "score_summary": f"Error: {str(e)}",
            "reasoning":"EVALUATION FAILED",
            "status": "success",
        }

        

@observe(as_type="chain", name="Non Branded Evaluation")
def evaluate_nonbranded_summary(nonbranded_data: Dict[str, Any], full_instruction_prompt: str, brand: str, trace_id: str):
    """Evaluate the top_non_branded summary + keywords context."""
    summary = nonbranded_data.get("summary", "")
    keywords = nonbranded_data.get("keywords", [])
    langfuse.update_current_trace(
       name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={
            "brand": brand,
            "evaluation_version": "1.2",
            "model_primary": "claude-opus-4-1",
            "model_context": "gpt-4.1"
        },
        user_id=f"raghvendra"
    )
    try:
        datapoint = {"summary": summary, "keywords": keywords}
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_results = parse_scores_for_single_output(llm_output)
        normalized_score = score_results["normalized_score"]

        trace_id = langfuse.get_current_trace_id()

        # Attach all scores to the same top-level trace
        for dim, score in score_results["raw_scores"].items():
            if score is not None:
                langfuse.create_score(
                    name=f"non_branded_{dim}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )

        # Log weighted total score
        langfuse.create_score(
            name="non_branded_weighted_total_score",
            value=score_results["weighted_total"],
            trace_id=trace_id,
            data_type="NUMERIC", 
            comment=f"Weighted total score for Non Branded (Brand: {brand}). Sum of all dimension scores × weights."
        )
        
        # Log average score
        langfuse.create_score(
            name="non_branded_average_score",
            value=score_results["avg_score"],
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Average weighted score for Non Branded (Brand: {brand}). Weighted total ÷ number of dimensions."
        )
        
        # Log final normalized percentage score
        langfuse.create_score(
            name="non_branded_normalized_percentage",
            value=normalized_score,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Final normalized percentage score (0-100%) for Non Branded (Brand: {brand}). Primary evaluation metric."
        )
        
        print(f"Non Branded Keywords summary scored: {normalized_score:.1f}%")
        
        return {
            "type": "non branded_summary",
            "summary": summary,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
        
    except Exception as e:
        # Log failed evaluation with zero scores for all dimensions
        print(f" Error evaluating trend Non Branded Summary: {e}")
        
        trace_id = langfuse.get_current_trace_id()
        
        # Log zero scores for all dimensions
        dimensions = ["strategic", "non_obvious", "specificity", "impactful", "actionable"]
        for dim in dimensions:
            langfuse.create_score(
                name=f"non_branded_{dim}_score",
                value=0,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=f"Failed evaluation - {dim} score set to 0 for Non Branded Summary. Error: {str(e)}"
            )
        
        # Log zero aggregate scores
        langfuse.create_score(
            name="non_branded_weighted_total_score",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - weighted total set to 0 for Non Branded Summary. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="non_branded_average_score", 
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - average score set to 0 for Non Branded Summary. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="non_branded_normalized_percentage",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - normalized percentage set to 0 for Non Branded Summary. Error: {str(e)}"
        )
        
        return {
            "type": "non branded_summary",
            "summary": summary,
            "normalized_score": 0.0,
            "score_summary": f"Error: {str(e)}",
            "reasoning":"EVALUATION FAILED",
            "status": "success",
        }
        

@observe(as_type="chain", name="Single Trend Evaluation")
def evaluate_single_trend(datapoint: Dict[str, Any], full_instruction_prompt: str, trend_index: int, total_trends: int, brand: str, trace_id: str):
    """Evaluate a single trend analysis datapoint."""
    trend_text = datapoint.get("trend", "N/A")

    langfuse.update_current_trace(
       name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={
            "brand": brand,
            "trend_index": trend_index,
            "total_trends": total_trends,
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
                    name=f"{dim}_score",
                    value=score,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                    comment=f"{dim.replace('_', ' ').title()} evaluation score (1-3 scale) for trend: {trend_index}"
                )
        
        # Log weighted total score
        langfuse.create_score(
            name="weighted_total_score",
            value=score_results["weighted_total"],
            trace_id=trace_id,
            data_type="NUMERIC", 
            comment=f"Weighted total score for {trend_index} (Brand: {brand}). Sum of all dimension scores × weights."
        )
        
        # Log average score
        langfuse.create_score(
            name="average_score",
            value=score_results["avg_score"],
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Average weighted score for {trend_index} (Brand: {brand}). Weighted total ÷ number of dimensions."
        )
        
        # Log final normalized percentage score
        langfuse.create_score(
            name="normalized_percentage",
            value=normalized_score,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Final normalized percentage score (0-100%) for {trend_index} (Brand: {brand}). Primary evaluation metric."
        )
        
        print(f" Trend '{trend_index}' scored: {normalized_score:.1f}%")
        
        return {
            "type": "trend_analysis",
            "trend": trend_text,
            "normalized_score": score_results["normalized_score"],
            "score_summary": score_results["detailed_summary"],
            "reasoning": llm_output,
            "status": "success",
        }
        
    except Exception as e:
        # Log failed evaluation with zero scores for all dimensions
        print(f" Error evaluating trend '{trend_index}': {e}")
        
        trace_id = langfuse.get_current_trace_id()
        
        # Log zero scores for all dimensions
        dimensions = ["strategic", "non_obvious", "specificity", "impactful", "actionable"]
        for dim in dimensions:
            langfuse.create_score(
                name=f"{dim}_score",
                value=0,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=f"Failed evaluation - {dim} score set to 0 for {trend_index}. Error: {str(e)}"
            )
        
        # Log zero aggregate scores
        langfuse.create_score(
            name="weighted_total_score",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - weighted total set to 0 for {trend_index}. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="average_score", 
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - average score set to 0 for {trend_index}. Error: {str(e)}"
        )
        
        langfuse.create_score(
            name="normalized_percentage",
            value=0.0,
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=f"Failed evaluation - normalized percentage set to 0 for {trend_index}. Error: {str(e)}"
        )
        
        return {
            "type": "trend_analysis",
            "trend": trend_text,
            "normalized_score": 0.0,
            "score_summary": f"Error: {str(e)}",
            "reasoning": "EVALUATION FAILED",
            "status": "failed"
        }


@observe(as_type="chain", name="Keyword Evaluation Pipeline 1.2")
def pipeline(input_path: str, output_path: str, brand: str):
    """Main pipeline for keyword analysis evaluation (1.2)."""
    data = load_suggestion_data(input_path)
    full_prompt = instruction_prompt_1_2 + "\n\n" + get_company_context(brand)

    results = []

    # Create a single top-level trace for the whole pipeline
    trace_id = langfuse.update_current_trace(
        name=f"{brand} Keyword Pipeline - {datetime.now().strftime('%Y-%m-%d')}",
        metadata={"brand": brand, "evaluation_type": "pipeline"},
        tags=["pipeline", "keyword-analysis", brand.lower()],
        user_id="raghvendra",
    )

    search_volume_analysis = data.get("search_volume_analysis", {})
    is_segmented = search_volume_analysis.get("is_segmented", False)

    if is_segmented:
        segmented = search_volume_analysis.get("segmented_analysis", {})
        for segment_name, segment_data in segmented.items():
            # Branded inside segment
            branded = segment_data.get("top_branded", {})
            if branded:
                results.append(
                    evaluate_branded_summary(
                        branded, 
                        full_prompt, 
                        f"{brand} - {segment_name}"
                    )
                )

            # Non-branded inside segment
            nonbranded = segment_data.get("top_non_branded", {})
            if nonbranded:
                results.append(
                    evaluate_nonbranded_summary(
                        nonbranded, 
                        full_prompt, 
                        f"{brand} - {segment_name}"
                    )
                )

    else:
        # Existing normal mode
        branded = search_volume_analysis.get("top_branded", {})
        if branded:
            results.append(evaluate_branded_summary(branded, full_prompt, brand))

        nonbranded = search_volume_analysis.get("top_non_branded", {})
        if nonbranded:
            results.append(evaluate_nonbranded_summary(nonbranded, full_prompt, brand))
    # Trend Analysis
    
    
    trends = data.get("trend_analysis", [])
    for idx, trend in enumerate(trends, 1):
        results.append(evaluate_single_trend(trend, full_prompt, idx, len(trends), brand, trace_id))

    # Save results to CSV
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)

    return results
