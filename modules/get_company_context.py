import os
from openai import OpenAI
from langfuse import get_client,observe
langfuse = get_client()
@observe(as_type="generation", name="Get Brand Context")
def get_company_context(company_name: str) -> str:
    """
    Fetches essential business and marketing context for a given company.
    Uses OpenAI API and reads key from environment variable OPENAI_API_KEY.
    
    Args:
        company_name (str): The name of the company to fetch context for.
    
    Returns:
        str: A detailed context summary about the company in a fixed schema.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables.")
    
    client = OpenAI(api_key=api_key)
    
    system_prompt = """
    You are a business analyst.
    Given the company name, return essential context about their business, 
    including: core business segments, product focus, geographic presence, 
    customer base, growth strategy, and what they do NOT do.
    Always return the company context 
    in the following structured schema :

    [Company Name]: Company Overview, Business Segments & Marketing Context

    Core Business Segments
    1. Segment Name
       - Product Focus: ...
       - Market Leadership: ...
       - Innovation: ...
       - Geographic Growth: ...
       - Audience: ...

    2. Segment Name
       - Product Focus: ...
       - Growth Drivers: ...
       - Key Clients: ...
       - Strategy: ...

    3. Segment Name
       - Service Focus: ...
       - Market Position: ...
       - Consultative Approach: ...

    Comprehensive Business and Marketing Strategies
    - Global Reach: ...
    - Brand Differentiation: ...
    - Expansion Goals: ...
    - Product & Service Innovation: ...

    Search Marketing Optimization Insights
    - Keyword & Content Focus: ...
    - Messaging Priorities: ...
    - Campaign Localization: ...
    - Multi-Channel Approach: ...

    What [Company Name] Does Not Do
    - Clearly list industries or products outside their scope.

    Be structured, concise, and business-relevant. 
    Do not invent unrelated industries or random details.
    """
    
    # ---- Call OpenAI ----
    response = client.chat.completions.create(
        model="gpt-4.1-2025-04-14",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": company_name}
        ],
        temperature=0.2,
    )

    # ---- Extract usage safely ----
    usage = getattr(response, "usage", {})
    input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0)
    total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)

    # ---- Pricing for GPT-4.1 (128k) ----
    input_cost = (input_tokens / 1_000_000) * 5
    output_cost = (output_tokens / 1_000_000) * 15
    total_cost = input_cost + output_cost

    # ---- Log to Langfuse ----
    langfuse.update_current_generation(
        input={"system_prompt": system_prompt, "company_name": company_name},
        output=response.choices[0].message.content,
        model="gpt-4.1-2025-04-14",
        usage_details={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
        cost_details={
            "input": input_cost,
            "output": output_cost,
            "total": total_cost,
        }
    )

    return response.choices[0].message.content.strip()


