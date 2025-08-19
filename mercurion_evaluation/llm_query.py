import os
from openai import OpenAI

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
    
    response = client.chat.completions.create(
        model="gpt-4.1-2025-04-14",  # swap if you prefer another GPT model
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": company_name}
        ],
        temperature=0.2,
    )
    
    return response.choices[0].message.content.strip()


