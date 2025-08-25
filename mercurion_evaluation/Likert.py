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


