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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file. Please set it before using the library.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

@observe(name="Claude LLM Call")
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

    return message.content[0].text

@observe(name="Claude LLM Call for url extraction")
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

