"""PredictionService: phased ML delivery (Constitution Principle 15).

Phase 1 (statistics): rolling averages, percentiles, standard deviation.
Phase 2 (predictive): linear regression for next-score prediction.
XGBoost is deferred until Phase 2 hardening; explainability first.
"""

import logging
import math
from typing import Optional

from src.models.predictive_insight import PredictiveInsight

logger = logging.getLogger(__name__)

BASELINE_SCORE = 70.0
MIN_RECORDS_FOR_REGRESSION = 5
PLATEAU_TOLERANCE = 1.0
PLATEAU_WINDOW = 5


class PredictionService:
    """Next-score prediction with plateau risk and confidence interval."""

    def predict(self, athlete_id: str, scores: list[float]) -> PredictiveInsight:
        clean = [float(s) for s in scores if s is not None]

        if len(clean) < 2:
            # Baseline average fallback for new swimmers.
            return PredictiveInsight(
                athlete_id=athlete_id,
                next_score_prediction=BASELINE_SCORE,
                plateau_risk=False,
                confidence_interval=5.0,
            )

        prediction = self._next_score(clean)
        ci = self._confidence_interval(clean, prediction)
        plateau = self._plateau_risk(clean)

        return PredictiveInsight(
            athlete_id=athlete_id,
            next_score_prediction=round(prediction, 2),
            plateau_risk=plateau,
            confidence_interval=round(ci, 2),
        )

    # ------------------------------------------------------------------
    # Phase 1 statistics
    # ------------------------------------------------------------------

    @staticmethod
    def rolling_average(scores: list[float], window: int = 3) -> list[float]:
        if window <= 0:
            raise ValueError("window must be positive")
        result = []
        for i in range(len(scores)):
            chunk = scores[max(0, i - window + 1) : i + 1]
            result.append(sum(chunk) / len(chunk))
        return result

    @staticmethod
    def percentile(scores: list[float], pct: float) -> Optional[float]:
        if not scores:
            return None
        ordered = sorted(scores)
        k = (len(ordered) - 1) * (pct / 100.0)
        low = math.floor(k)
        high = math.ceil(k)
        if low == high:
            return ordered[int(k)]
        return ordered[low] * (high - k) + ordered[high] * (k - low)

    @staticmethod
    def std_dev(scores: list[float]) -> float:
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)
        return math.sqrt(variance)

    # ------------------------------------------------------------------
    # Phase 2 predictive
    # ------------------------------------------------------------------

    def _next_score(self, scores: list[float]) -> float:
        if len(scores) < MIN_RECORDS_FOR_REGRESSION:
            return self.rolling_average(scores, window=min(3, len(scores)))[-1]
        return self._linear_regression_next(scores)

    @staticmethod
    def _linear_regression_next(scores: list[float]) -> float:
        n = len(scores)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(scores) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, scores))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        slope = cov / var_x if var_x else 0.0
        intercept = mean_y - slope * mean_x
        return intercept + slope * n

    def _confidence_interval(self, scores: list[float], prediction: float) -> float:
        spread = self.std_dev(scores)
        return max(spread * 1.96, 0.5)

    @staticmethod
    def _plateau_risk(scores: list[float]) -> bool:
        if len(scores) < PLATEAU_WINDOW:
            return False
        recent = scores[-PLATEAU_WINDOW:]
        return all(
            abs(recent[i] - recent[i - 1]) < PLATEAU_TOLERANCE for i in range(1, len(recent))
        )


def get_prediction_service() -> PredictionService:
    return PredictionService()
