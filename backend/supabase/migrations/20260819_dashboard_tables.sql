-- Dashboard-specific tables migration
-- Creates tables for as_daily_aggregations (materialized view), as_predictive_insights, as_coaching_recommendations, as_competition_results_browser_widgets

-- Daily Aggregations Materialized View (for dashboard performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS as_daily_aggregations AS
SELECT 
    athlete_id,
    date,
    AVG(figure_score) as avg_figure_score,
    AVG(routine_score) as avg_routine_score,
    AVG(figure_score) as rolling_trend
FROM (
    SELECT 
        mfr.athlete_name as athlete_id,
        m.meet_date as date,
        mfr.figure_score,
        NULL as routine_score
    FROM as_meet_figure_result mfr
    JOIN as_meet m ON mfr.meet_id = m.id
    UNION ALL
    SELECT 
        mrr.team_athletes->>0 as athlete_id,
        m.meet_date as date,
        NULL as figure_score,
        mrr.routine_score
    FROM as_meet_routine_result mrr
    JOIN as_meet m ON mrr.meet_id = m.id
) combined
GROUP BY athlete_id, date;

-- Create unique index for materialized view refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_as_daily_aggregations_athlete_date ON as_daily_aggregations(athlete_id, date);

-- Predictive Insights table
CREATE TABLE IF NOT EXISTS as_predictive_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID NOT NULL,
    next_score_prediction NUMERIC,
    plateau_risk BOOLEAN DEFAULT FALSE,
    confidence_interval NUMERIC,
    model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_as_predictive_insights_athlete ON as_predictive_insights(athlete_id);

-- Coaching Recommendations table
CREATE TABLE IF NOT EXISTS as_coaching_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID NOT NULL,
    recommendation_text TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    weakest_figure TEXT,
    model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_as_coaching_recommendations_athlete ON as_coaching_recommendations(athlete_id);

-- Competition Results Browser Widgets table (for user widget preferences)
CREATE TABLE IF NOT EXISTS as_competition_results_browser_widgets (
    widget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id UUID NOT NULL REFERENCES as_club(id),
    user_id UUID NOT NULL,
    tree_state JSONB DEFAULT '{}',
    active_tab TEXT DEFAULT 'figures' CHECK (active_tab IN ('figures', 'routines')),
    selected_node_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_as_competition_results_browser_widgets_user ON as_competition_results_browser_widgets(user_id);
CREATE INDEX IF NOT EXISTS idx_as_competition_results_browser_widgets_club ON as_competition_results_browser_widgets(club_id);

-- RLS for dashboard tables
ALTER TABLE as_predictive_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE as_coaching_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE as_competition_results_browser_widgets ENABLE ROW LEVEL SECURITY;

-- RLS Policies for as_predictive_insights
CREATE POLICY "Users can view predictive insights for their club athletes" ON as_predictive_insights
    FOR SELECT USING (
        athlete_id IN (
            SELECT id FROM as_athlete WHERE club_id = (
                SELECT club_id FROM as_coach WHERE id = auth.uid()
                UNION SELECT club_id FROM as_athlete WHERE id = auth.uid()
            )
        )
    );

-- RLS Policies for as_coaching_recommendations
CREATE POLICY "Users can view coaching recommendations for their club athletes" ON as_coaching_recommendations
    FOR SELECT USING (
        athlete_id IN (
            SELECT id FROM as_athlete WHERE club_id = (
                SELECT club_id FROM as_coach WHERE id = auth.uid()
                UNION SELECT club_id FROM as_athlete WHERE id = auth.uid()
            )
        )
    );

-- RLS Policies for as_competition_results_browser_widgets
CREATE POLICY "Users can view their own widget config" ON as_competition_results_browser_widgets
    FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert their own widget config" ON as_competition_results_browser_widgets
    FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can update their own widget config" ON as_competition_results_browser_widgets
    FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Users can delete their own widget config" ON as_competition_results_browser_widgets
    FOR DELETE USING (user_id = auth.uid());

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_as_daily_aggregations()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY as_daily_aggregations;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON as_daily_aggregations TO authenticated;
GRANT SELECT ON as_predictive_insights TO authenticated;
GRANT SELECT ON as_coaching_recommendations TO authenticated;
GRANT ALL ON as_competition_results_browser_widgets TO authenticated;