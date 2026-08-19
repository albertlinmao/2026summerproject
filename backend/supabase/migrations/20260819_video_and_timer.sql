CREATE TABLE IF NOT EXISTS video_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id UUID NOT NULL REFERENCES club(id),
  uploaded_by UUID NOT NULL,
  storage_path TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'video/mp4',
  size_bytes INTEGER NOT NULL,
  duration_seconds NUMERIC,
  status TEXT NOT NULL DEFAULT 'uploading' CHECK (status IN ('uploading', 'uploaded', 'ready')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS video_markers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID NOT NULL REFERENCES video_uploads(id) ON DELETE CASCADE,
  time_offset NUMERIC(10,3) NOT NULL,
  marker_type TEXT NOT NULL CHECK (marker_type IN ('audio_cue', 'figure', 'timing_mark')),
  figure_id TEXT,
  label TEXT,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_video_markers_video_offset ON video_markers(video_id, time_offset);

CREATE TABLE IF NOT EXISTS routine_timers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id UUID NOT NULL REFERENCES club(id),
  title TEXT,
  duration_seconds NUMERIC NOT NULL,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE video_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_markers ENABLE ROW LEVEL SECURITY;
ALTER TABLE routine_timers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view videos in their club" ON video_uploads
  FOR SELECT USING (club_id = (SELECT club_id FROM athlete WHERE id = auth.uid()));
CREATE POLICY "Users can insert videos in their club" ON video_uploads
  FOR INSERT WITH CHECK (club_id = (SELECT club_id FROM athlete WHERE id = auth.uid()));
CREATE POLICY "Users can view markers for their club videos" ON video_markers
  FOR SELECT USING (video_id IN (SELECT id FROM video_uploads WHERE club_id = (SELECT club_id FROM athlete WHERE id = auth.uid())));
CREATE POLICY "Users can insert markers for their club videos" ON video_markers
  FOR INSERT WITH CHECK (video_id IN (SELECT id FROM video_uploads WHERE club_id = (SELECT club_id FROM athlete WHERE id = auth.uid())));
CREATE POLICY "Users can view timers in their club" ON routine_timers
  FOR SELECT USING (club_id = (SELECT club_id FROM athlete WHERE id = auth.uid()));
CREATE POLICY "Users can insert timers in their club" ON routine_timers
  FOR INSERT WITH CHECK (club_id = (SELECT club_id FROM athlete WHERE id = auth.uid()));
