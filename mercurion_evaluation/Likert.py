import os
import json
from dotenv import load_dotenv
import anthropic

repo_root = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(repo_root, ".env")

load_dotenv(dotenv_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file. Please set it before using the library.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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

def extract_urls_and_claims(suggestion_data):
    """
    Ask Claude to extract URLs and numeric/statistical claims from any message.
    Returns normalized dict.
    """
    system_prompt = """You are a precise information extractor.
    Given any text or JSON, extract:
    1. All URLs.
    2. All numerical/statistical claims (amounts, percentages, years, market sizes).
    Return as list of dicts: {{"url";"","claim";""},......}"""

    resp = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": suggestion_data}],
        temperature=0.1
    )

    try:
        return json.loads(resp.content[0].text)
    except:
        return []

def evaluate_url(extracted_items):
    """
    Takes a list of dicts like [{"url": "...", "claim": "..."}].
    Uses Claude with web_search tool to check validity of each claim.
    Returns a list of dicts: [{"url": "...", "claim": "...", "result": "pass/fail"}]
    """
    results = []

    for item in extracted_items:
        url = item.get("url", "")
        claim = item.get("claim", "")

        query = f"""
        Verify the following claim using web search.
        Claim: "{claim}"
        Source URL (if relevant): {url}
        Return ONLY JSON in format:
        {{"url": "{url}", "claim": "{claim}", "result": "pass" or "fail"}}
        """

        response = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=500,
            messages=[{"role": "user", "content": query}],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            }],
            temperature=0.1
        )

        try:
            parsed = json.loads(response.content[0].text)
            results.append(parsed)
        except Exception:
            results.append({
                "url": url,
                "claim": claim,
                "result": "fail"   # default fail if parsing breaks
            })

    return results
