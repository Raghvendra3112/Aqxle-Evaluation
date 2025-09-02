""" INPUT FORMAT -- 
{
   ANY OTHER FIELD OPTIONAL
  "top_k_trends": [
    {
      "trend": "",
      "score": ,
      "top_keywords": [
        [ "keyword1", score
        ],...... n keywords
      ],
      "adcopies": [
        { "keyword": ", "title": "", "description": "", "visible_url": "", "search_volume": ""
        }, ...... n ad copies
      ],
      "analysis": {
        "trend_analyzed": "",
        "executive_summary": "",
        "strategic_market_context": [
          ],
        "key_findings": {},
        "actionable_recommendations": {
            }
          ]
        }
      }
    }
  ]
}

OUTPATH PATH - must be csv

"""

from openai import OpenAI
import anthropic
import json
import sys
import os
import pandas as pd
import re

from prompts.prompts import instruction_prompt_1_3
from modules.eval_functions import evaluate
from modules.get_company_context import get_company_context


def load_suggestion_data(file_path: str):
    
    """Load Ad copy analysis json and return list of top_k_trends as dicts."""
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("top_k_trends", [])



def parse_scores(llm_output: str):
    """
    Parse dimension scores (1-3 scale) and compute weighted + normalized scores.
    Returns a dict with both raw + calculated values.
    """
    dimensions = {
        "strategic": 0.2,
        "non_obvious": 0.1,
        "specificity": 0.2,
        "impactful": 0.2,
        "clarity": 0.1,
        "actionable":0.2
    }
    parsed_scores={}
    weighted_scores={}

    llm_output = llm_output.strip()
    if llm_output.startswith("```"):
        llm_output = re.sub(r"^```(?:json)?", "", llm_output, flags=re.IGNORECASE).strip()
        llm_output = re.sub(r"```$", "", llm_output).strip()
    
    try:
       output_dict =  json.loads(llm_output)
    except json.JSONDecodeError as e:
        with open("broken_llm_output.json", "w", encoding="utf-8") as f:
            f.write(llm_output)
        raise ValueError(f"Still not valid JSON: {e}")
 

    # Extract raw + weighted scores
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
    summary_lines.append(f"Average Score: {avg_score:.2f} out of 0.5")
    summary_lines.append(f"Normalized Score: {normalized_pct:.2f}%")


    return "\n".join(summary_lines)


def pipeline(input, output, brand):
    input_path = input
    output_path =  output
  
    company_context = get_company_context(brand)
    full_instruction_prompt = instruction_prompt_1_3 + f"\n\nAdditional context about Brand:\n{company_context}"
  
    suggestion_data = load_suggestion_data(input_path)
    results = []

    for i, datapoint in enumerate(suggestion_data, 1):
        print(f"=== Evaluating trend {i}/{len(suggestion_data)}: {datapoint['trend']} ===")

        llm_output = evaluate(datapoint, full_instruction_prompt)
        score_summary = parse_scores(llm_output)
            
        analysis = datapoint.get("analysis", {})

            
        results.append({
            "trend": datapoint["trend"],
            "industry_score": datapoint["industry_score"],
            "analysis": json.dumps(datapoint.get("analysis", {}), indent=2, ensure_ascii=False),
            "score_summary": score_summary,
            #"citation_score": json.dumps(url_score, indent=2, ensure_ascii=False),
            "reasoning": llm_output
        })
            
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nEvaluation completed. Results saved to {output_path}")
