import os
import json
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

import anthropic  
from langfuse import get_client,observe

repo_root = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(repo_root, ".env")

load_dotenv(dotenv_path)
langfuse = get_client()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file. Please set it before using the library.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@observe(as_type="generation", name="Claude LLM Call")
def evaluate(suggestion_data, system_prompt):
    """
    Evaluate suggestions using Anthropic's Claude model.

    Parameters:
        suggestion_data (dict): The data to evaluate (will be JSON serialized).
        system_prompt (str): The system-level instructions for the model.

    Returns:
        str: The model's response text.
    """
    if not isinstance(suggestion_data, (dict, list)):
        raise TypeError("suggestion_data must be a dictionary or list.")

    message = client.messages.create(
        model="claude-opus-4-1-20250805",  # Opus 4.1
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(suggestion_data)}],
        temperature=0.1
    )
    # Extract usage safely
    usage = getattr(message, "usage", {})
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    cache_write_tokens = getattr(usage, "cache_write_input_tokens", 0)
    cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0)

    # ---- Pricing (Anthropic Claude Opus 4.1 as of Sep 2025) ----
    # Input: $15 / MTok
    # Output: $75 / MTok
    # Prompt caching: Write $18.75 / MTok, Read $1.50 / MTok
    input_cost = (input_tokens / 1_000_000) * 15
    output_cost = (output_tokens / 1_000_000) * 75
    cache_write_cost = (cache_write_tokens / 1_000_000) * 18.75
    cache_read_cost = (cache_read_tokens / 1_000_000) * 1.5
    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

    # ---- Log to Langfuse ----
    langfuse.update_current_generation(
        input={"system_prompt": system_prompt, "user_input": suggestion_data},
        model="claude-opus-4-1-20250805",
        usage_details={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_write_tokens": cache_write_tokens,
            "cache_read_tokens": cache_read_tokens,
            "total_tokens": input_tokens + output_tokens + cache_write_tokens + cache_read_tokens,
        },
        cost_details={
            "input": input_cost,
            "output": output_cost,
            "cache_write": cache_write_cost,
            "cache_read": cache_read_cost,
            "total": total_cost,
        }
    )

    return message.content[0].text

@observe(as_type="tool", name="Claude LLM Call for url extraction")
def url_extracter_1_3(suggestion_data):
    """
    Extract URLs and numeric/statistical claims from any message.
    Returns normalized dict.
    """
    system_prompt = """You are a precise information extractor.
    Given any text or JSON, extract:
    1. All URLs (complete URLs starting with http/https).
    2. All numerical/statistical claims that is based on that URL (amounts, percentages, years, market sizes, revenue figures).
    
    Return ONLY a JSON array of objects in this exact format:
    [{"url": "complete_url_here", "claim": "specific_claim_text"}, ...]
    
    If no URLs or claims found, return: []
    
    Important: 
    - Extract complete URLs, not partial ones
    - Extract specific numerical claims with context
    - Return valid JSON only, no other text"""

    if not isinstance(suggestion_data, str):
        suggestion_data = json.dumps(suggestion_data, indent=2)

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": suggestion_data}
                    ]
                }
            ],
            temperature=0.1
        )

        raw_output = resp.content[0].text.strip()
        
        if raw_output.startswith('[') and raw_output.endswith(']'):
            return json.loads(raw_output)
        elif '[' in raw_output and ']' in raw_output:
            start = raw_output.find('[')
            end = raw_output.rfind(']') + 1
            json_part = raw_output[start:end]
            return json.loads(json_part)
        else:
            return json.loads(raw_output)
            
    except json.JSONDecodeError as e:
        print("WARNING: JSON parse failed:", str(e))
        print("Raw model output:", raw_output)
        return []
    except Exception as e:
        print("WARNING: Extraction failed:", str(e))
        return []

