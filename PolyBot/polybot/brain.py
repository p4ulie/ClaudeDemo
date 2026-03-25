"""
Layer 2: AI Brain.
Uses Claude API to estimate probabilities for Polymarket markets.
Sends structured JSON prompts and parses responses for probability estimates.
Supports prompt versioning to track iterations from v1 to production.
"""

import json
import logging
from dataclasses import dataclass
import httpx
from polybot.config import AIConfig
from polybot.prompts import v1 as prompt_v1

logger = logging.getLogger(__name__)


@dataclass
class ProbabilityEstimate:
    """Claude's probability estimate for a market outcome."""
    market_question: str
    estimated_probability: float
    confidence: float  # 0-1 scale, how confident Claude is in its estimate
    reasoning: str
    prompt_version: str


class AIBrain:
    """
    AI-powered probability estimation engine.
    Sends market data to Claude API and receives structured probability estimates.
    Uses httpx for async HTTP calls and structured JSON prompts for parseable output.
    """

    def __init__(self, cfg: AIConfig):
        self.api_key = cfg.api_key
        self.model = cfg.model
        self.max_tokens = cfg.max_tokens
        self.prompt_version = prompt_v1.VERSION
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("AIBrain initialized with model=%s, prompt=%s", self.model, self.prompt_version)

    async def estimate_probability(
        self,
        question: str,
        current_price: float,
        market_volume: float,
        additional_context: str = "",
    ) -> ProbabilityEstimate:
        """
        Ask Claude to estimate the true probability of a market outcome.
        Returns structured estimate with reasoning.
        """
        # Build the structured prompt requesting JSON output
        user_message = prompt_v1.build_prompt(
            question=question,
            current_price=current_price,
            market_volume=market_volume,
            additional_context=additional_context,
        )

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "user", "content": user_message},
            ],
            "system": prompt_v1.SYSTEM_PROMPT,
        }

        response = await self._client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        # Parse the structured JSON response from Claude
        content = data["content"][0]["text"]
        estimate = self._parse_response(content, question)
        logger.info(
            "Estimate for '%s': p=%.3f (confidence=%.2f)",
            question[:50], estimate.estimated_probability, estimate.confidence,
        )
        return estimate

    def _parse_response(self, content: str, question: str) -> ProbabilityEstimate:
        """
        Parse Claude's JSON response into a ProbabilityEstimate.
        Falls back to conservative defaults if parsing fails.
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            return ProbabilityEstimate(
                market_question=question,
                estimated_probability=float(parsed["probability"]),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=parsed.get("reasoning", ""),
                prompt_version=self.prompt_version,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse AI response: %s", e)
            # Conservative fallback: return 0.5 (no edge) so no trade is placed
            return ProbabilityEstimate(
                market_question=question,
                estimated_probability=0.5,
                confidence=0.0,
                reasoning=f"Parse error: {e}",
                prompt_version=self.prompt_version,
            )

    async def close(self):
        """Close the httpx client session."""
        await self._client.aclose()
