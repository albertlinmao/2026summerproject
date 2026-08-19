from datetime import datetime, timezone

from openai import OpenAI, OpenAIError, APITimeoutError

from src.models.insights import CoachingRecommendation


class AIServiceUnavailableError(Exception):
    pass


_client = OpenAI()

SYSTEM_PROMPT = (
    "You are an expert artistic swimming coach. "
    "Given an athlete's recent competition scores, provide a concise, actionable coaching recommendation. "
    "Identify the weakest figure and suggest a specific drill or focus area."
)


def generate_coaching_recommendation(
    athlete_id: str,
    recent_scores: list[dict],
) -> CoachingRecommendation:
    score_text = "\n".join(
        f"- Figure: {s.get('figure_name', 'unknown')}, Score: {s.get('score', 0)}"
        for s in recent_scores
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Athlete ID: {athlete_id}\n\nRecent scores:\n{score_text}\n\n"
                        "Provide: 1) a coaching recommendation, 2) the weakest figure name."
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )

        content = response.choices[0].message.content or ""

        weakest_figure = ""
        recommendation_text = content
        for line in content.split("\n"):
            lower = line.lower()
            if "weakest" in lower or "figure" in lower:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    weakest_figure = parts[1].strip().strip("*").strip()
                    break

        return CoachingRecommendation(
            athlete_id=athlete_id,
            recommendation_text=recommendation_text,
            generated_at=datetime.now(timezone.utc),
            weakest_figure=weakest_figure,
        )

    except (OpenAIError, APITimeoutError, TimeoutError, ConnectionError) as exc:
        raise AIServiceUnavailableError(f"OpenAI request failed: {exc}") from exc
