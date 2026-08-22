"""AICoachService: LLM coaching recommendations (Principle 15 Phase 3).

Read-only regarding core data (Principle 11). Falls back to a baseline
average recommendation for new swimmers and raises AIServiceUnavailableError
when the OpenAI service cannot be reached so callers can degrade gracefully.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from openai import APITimeoutError, OpenAI, OpenAIError

from src.core.config import get_settings
from src.models.coaching_recommendation import CoachingRecommendation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert artistic swimming coach. Given an athlete's recent "
    "competition scores, provide one concise, actionable practice focus. "
    "Identify the weakest figure and suggest a specific drill."
)

AI_UNAVAILABLE_TEXT = "AI temporarily unavailable"


class AIServiceUnavailableError(Exception):
    """Raised when the external AI coach service is unreachable or misconfigured."""


class AICoachService:
    def __init__(self, client: Optional[OpenAI] = None):
        self._client = client

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = get_settings().OPENAI_API_KEY
            if not api_key:
                raise AIServiceUnavailableError("OPENAI_API_KEY is not configured")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def generate_recommendation(
        self,
        athlete_id: str,
        athlete_name: str,
        scores: list[float],
        figure_averages: Optional[dict[str, float]] = None,
    ) -> CoachingRecommendation:
        """Generate a natural language practice focus for an athlete.

        Raises AIServiceUnavailableError when the AI provider fails; callers
        must fall back to AI_UNAVAILABLE_TEXT messaging.
        """
        if len(scores) < 2:
            # Baseline average fallback for new swimmers (no history to analyze).
            return CoachingRecommendation(
                athlete_id=athlete_id,
                recommendation_text=(
                    f"{athlete_name or 'This athlete'} is new to competition tracking. "
                    "Focus on fundamentals across all figures and establish baseline scores."
                ),
                generated_at=datetime.now(timezone.utc),
                weakest_figure="",
            )

        weakest = ""
        if figure_averages:
            weakest = min(figure_averages, key=figure_averages.get)

        score_lines = "\n".join(f"- {s:.2f}" for s in scores[-10:])
        figure_lines = (
            "\n".join(f"- {k}: {v:.2f}" for k, v in sorted(figure_averages.items()))
            if figure_averages
            else "(not available)"
        )

        try:
            response = self._get_client().chat.completions.create(
                model=get_settings().OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Athlete: {athlete_name}\n\n"
                            f"Recent total scores:\n{score_lines}\n\n"
                            f"Average scores per figure:\n{figure_lines}\n\n"
                            "Provide: 1) a short coaching recommendation, "
                            "2) the weakest figure name on its own line prefixed with 'Weakest figure:'."
                        ),
                    },
                ],
                temperature=0.7,
                max_tokens=300,
            )
            content = (response.choices[0].message.content or "").strip()
        except (OpenAIError, APITimeoutError, TimeoutError, ConnectionError) as exc:
            logger.warning("AI coach unavailable for athlete %s: %s", athlete_id, exc)
            raise AIServiceUnavailableError(str(exc)) from exc

        return CoachingRecommendation(
            athlete_id=athlete_id,
            recommendation_text=content,
            generated_at=datetime.now(timezone.utc),
            weakest_figure=self._extract_weakest(content) or weakest,
        )

    @staticmethod
    def _extract_weakest(content: str) -> str:
        for line in content.splitlines():
            lower = line.lower()
            if "weakest figure" in lower and ":" in line:
                return line.split(":", 1)[1].strip().strip("*").strip()
        return ""


def get_ai_coach_service() -> AICoachService:
    return AICoachService()
