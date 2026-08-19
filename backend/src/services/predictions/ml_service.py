import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from src.models.insights import PredictiveInsight


def predict_next_score(
    athlete_id: str,
    historical_scores: list[dict],
) -> PredictiveInsight:
    if len(historical_scores) < 2:
        return PredictiveInsight(
            athlete_id=athlete_id,
            next_score_prediction=70.0,
            plateau_risk=False,
            confidence_interval=5.0,
        )

    scores = [h["score"] for h in historical_scores]
    X = np.arange(len(scores)).reshape(-1, 1)
    y = np.array(scores, dtype=float)

    model = XGBRegressor(n_estimators=50, max_depth=3, verbosity=0, random_state=42)
    model.fit(X, y)

    next_X = np.array([[len(scores)]])
    prediction = float(model.predict(next_X)[0])

    preds_all = model.predict(X)
    residuals = y - preds_all
    variance = float(np.var(residuals))
    confidence_interval = round(float(np.sqrt(variance) * 1.96), 2)

    flat = all(abs(scores[i] - scores[i - 1]) < 1.0 for i in range(-5, 0)) if len(scores) >= 5 else False
    plateau_risk = flat

    return PredictiveInsight(
        athlete_id=athlete_id,
        next_score_prediction=round(prediction, 2),
        plateau_risk=plateau_risk,
        confidence_interval=confidence_interval,
    )


def predict_baseline_average(club_id: str) -> float:
    from src.core.database import supabase

    response = (
        supabase.table("competition_results")
        .select("score")
        .eq("club_id", club_id)
        .execute()
    )

    rows = response.data or []

    athletes_with_few_records = {}
    for row in rows:
        athlete_id = row.get("athlete_id", "")
        athletes_with_few_records.setdefault(athlete_id, []).append(row.get("score", 0))

    sparse_averages = []
    for aid, scores_list in athletes_with_few_records.items():
        if len(scores_list) < 5:
            sparse_averages.append(np.mean(scores_list))

    if sparse_averages:
        return round(float(np.mean(sparse_averages)), 2)

    return 70.0
