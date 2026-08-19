from src.models.aggregations import TeamOverview, HeatmapData

def get_coach_team_overview(coach_id: str) -> TeamOverview:
    # Logic to aggregate team heatmap data and predictions
    
    # T022: Predictive baseline average fallback logic for new athletes
    # If athlete has < 5 historical records, use age-group average baseline (e.g. 70.0)
    def calculate_prediction(historical_scores: list) -> float:
        if len(historical_scores) < 5:
            return 70.0 # Baseline fallback
        return sum(historical_scores) / len(historical_scores) # Simplistic ML mock
        
    return TeamOverview(
        coach_id=coach_id,
        team_heatmap=[
            HeatmapData(
                athlete_id='athlete-1', 
                figure_weaknesses={'spin': 5.2}, 
                prediction_score=calculate_prediction([]),
                figure_score=68.5,
                routine_score=72.0
            )
        ]
    )
