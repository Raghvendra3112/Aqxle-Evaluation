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

from prompts.prompts import instruction_prompt_1_2
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context


def load_suggestion_data(file_path: str):
    """
    Load CSV with two columns: Actionable News, Insight
    Returns a list of dicts: [{"Actionable News": ..., "Insight": ...}, ...]
    """
    df = pd.read_csv(file_path)

    #Check required columns
    expected_cols = {"Actionable News", "Insight"}
    if not expected_cols.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {expected_cols}")

    # Convert rows into list of dicts
    return df.to_dict(orient="records")



def parse_scores(llm_output: str):
    """
    Parse dimension scores (1-3 scale) and compute weighted + normalized scores.
    Returns a dict with both raw + calculated values.
    """
    dimensions = {
        "Strategic": 0.2,
        "Nonobvious": 0.15,
        "Specificity": 0.15,
        "Actionable": 0.3,
        "Impactful": 0.2
    }

    parsed_scores = {}
    weighted_scores = {}

     # --- CLEANING STEP ---
    # Strip markdown fences like ```json ... ```
    llm_output = llm_output.strip()
    if llm_output.startswith("```"):
        llm_output = re.sub(r"^```(?:json)?", "", llm_output, flags=re.IGNORECASE).strip()
        llm_output = re.sub(r"```$", "", llm_output).strip()
    
    # Convert string to Python dict
    try:
        output_dict = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output is not valid JSON")

    # Extract raw 1-3 score for each dimension
    for dim, weight in dimensions.items():
        if dim in output_dict and "score" in output_dict[dim]:
            parsed_scores[dim] = int(output_dict[dim]["score"])
            weighted_scores[dim] = parsed_scores[dim] * weight
        else:
            parsed_scores[dim] = None
            weighted_scores[dim] = 0.0

    # Average of weighted scores
    avg_score = sum(weighted_scores.values()) / len(dimensions)

    # Normalized percentage (relative to max possible = 0.6)
    normalized_pct = (avg_score / 0.6) * 100

    # Build summary string
    summary_lines = []
    for dim, weight in dimensions.items():
        summary_lines.append(
            f"{dim}: {parsed_scores[dim]} × {weight} = {weighted_scores[dim]:.2f}"
        )

    summary_lines.append(f"\nAverage Weighted Score: {avg_score:.2f} out of 0.6")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")

    return "\n".join(summary_lines)


def pipeline(input, output, brand):
    input_path = input
    output_path =  output
  
    company_context = get_company_context(brand)
    full_instruction_prompt = instruction_prompt_1_2 + f"\n\nAdditional context about Brand:\n{company_context}"
  
    suggestion_data = load_suggestion_data(input_path)
    results = []

    for i, datapoint in enumerate(suggestion_data, 1):
        print(f"=== Evaluating datapoint {i}/{len(suggestion_data)} ===")

    
        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_summary = parse_scores(llm_output)
       
        results.append({
            "news": datapoint["Actionable News"],
            "insight": datapoint["Insight"],
            "score_summary": score_summary,
            "reasoning": llm_output
        })

    pd.DataFrame(results).to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nEvaluation completed. Results saved to {output_path}")

