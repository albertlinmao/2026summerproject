CREATE TABLE IF NOT EXISTS as_video_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id UUID NOT NULL REFERENCES as_club(id),
  athlete_id UUID NOT NULL REFERENCES as_athlete(id),
  uploaded_by UUID NOT NULL,
  storage_path TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'video/mp4',
  size_bytes INTEGER NOT NULL,
  duration_seconds NUMERIC,
  status TEXT NOT NULL DEFAULT 'uploading' CHECK (status IN ('uploading', 'uploaded', 'ready')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS as_video_markers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID NOT NULL REFERENCES as_video_uploads(id) ON DELETE CASCADE,
  time_offset NUMERIC(10,3) NOT NULL,
  marker_type TEXT NOT NULL CHECK (marker_type IN ('audio_cue', 'figure', 'timing_mark')),
  figure_id TEXT,
  label TEXT,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_as_video_markers_video_offset ON as_video_markers(video_id, time_offset);

CREATE TABLE IF NOT EXISTS as_routine_timers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id UUID NOT NULL REFERENCES as_club(id),
  title TEXT,
  duration_seconds NUMERIC NOT NULL,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE as_video_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE as_video_markers ENABLE ROW LEVEL SECURITY;
ALTER TABLE as_routine_timers ENABLE ROW LEVEL SECURITY;

-- RLS Policies for as_video_uploads with family access (as_athlete, coaches, parents)
-- Uses the Multi-Tenant User Service claims: club_id, user_id, roles, athlete_ids (for parents)
CREATE POLICY "Users can view videos in their club" ON as_video_uploads
  FOR SELECT USING (
    club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
    OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
  );
CREATE POLICY "Family can view athlete's videos" ON as_video_uploads
  FOR SELECT USING (
    athlete_id = auth.uid()  -- as_athlete themselves
    OR athlete_id IN (SELECT jsonb_array_elements_text(coalesce(auth.jwt()->'athlete_ids', '[]'::jsonb))::uuid)  -- parents
  );
CREATE POLICY "Coaches can view their athletes' videos" ON as_video_uploads
  FOR SELECT USING (
    club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
  );
CREATE POLICY "Users can insert videos in their club" ON as_video_uploads
  FOR INSERT WITH CHECK (
    club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
    OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
  );
CREATE POLICY "Users can update their own videos" ON as_video_uploads
  FOR UPDATE USING (uploaded_by = auth.uid());

-- RLS Policies for as_video_markers
CREATE POLICY "Users can view markers for accessible videos" ON as_video_markers
  FOR SELECT USING (
    video_id IN (
      SELECT id FROM as_video_uploads WHERE 
        club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
        OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
        OR athlete_id = auth.uid()
        OR athlete_id IN (SELECT jsonb_array_elements_text(coalesce(auth.jwt()->'athlete_ids', '[]'::jsonb))::uuid)
    )
  );
CREATE POLICY "Users can insert markers for accessible videos" ON as_video_markers
  FOR INSERT WITH CHECK (
    video_id IN (
      SELECT id FROM as_video_uploads WHERE 
        club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
        OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
    )
  );

-- RLS Policies for as_routine_timers
CREATE POLICY "Users can view timers in their club" ON as_routine_timers
  FOR SELECT USING (
    club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
    OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
  );
CREATE POLICY "Users can insert timers in their club" ON as_routine_timers
  FOR INSERT WITH CHECK (
    club_id = (SELECT club_id FROM as_coach WHERE id = auth.uid())
    OR club_id = (SELECT club_id FROM as_athlete WHERE id = auth.uid())
  );
CREATE POLICY "Users can update their own timers" ON as_routine_timers
  FOR UPDATE USING (created_by = auth.uid());

-- Add updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_as_video_uploads_updated_at BEFORE UPDATE ON as_video_uploads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_as_routine_timers_updated_at BEFORE UPDATE ON as_routine_timers
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();