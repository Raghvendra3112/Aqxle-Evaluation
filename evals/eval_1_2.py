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

from prompts.prompts import instruction_prompt_1_2
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context


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

    llm_output = llm_output.strip()
    if llm_output.startswith("```"):
        llm_output = re.sub(r"^```(?:json)?", "", llm_output, flags=re.IGNORECASE).strip()
        llm_output = re.sub(r"```$", "", llm_output).strip()
    
    try:
        output_dict = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output is not valid JSON")


    for dim, weight in dimensions.items():
        if dim in output_dict and "score" in output_dict[dim]:
            parsed_scores[dim] = int(output_dict[dim]["score"])
            weighted_scores[dim] = parsed_scores[dim] * weight
        else:
            parsed_scores[dim] = None
            weighted_scores[dim] = 0.0


    avg_score = sum(weighted_scores.values()) / len(dimensions)

    normalized_pct = (avg_score / 0.6) * 100

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

