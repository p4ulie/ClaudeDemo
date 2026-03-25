"""
Prompt Version 1: Structured JSON probability estimation.
Each prompt version is a separate module to track iterations from v1 to production.
Change the VERSION string when modifying prompts to track which version produced each estimate.
"""

VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are a probability estimation engine for prediction markets. "
    "You analyze market questions and provide calibrated probability estimates. "
    "You must respond ONLY with valid JSON in the exact format specified. "
    "Your estimates should account for base rates, current events, and known biases. "
    "Be calibrated: when you say 70%, events should happen ~70% of the time."
)


def build_prompt(
    question: str,
    current_price: float,
    market_volume: float,
    additional_context: str = "",
) -> str:
    """
    Build the user message for probability estimation.
    Requests structured JSON output for reliable parsing.
    """
    context_block = ""
    if additional_context:
        context_block = f"\nAdditional Context: {additional_context}"

    return f"""Analyze this prediction market and estimate the true probability of the outcome.

Market Question: {question}
Current Market Price (implied probability): {current_price:.2f}
Market Volume (USDC): {market_volume:,.0f}{context_block}

Respond with ONLY this JSON format, no other text:
{{
    "probability": <float between 0.01 and 0.99>,
    "confidence": <float between 0.0 and 1.0, how confident you are>,
    "reasoning": "<brief explanation of your estimate, key factors considered>"
}}"""
