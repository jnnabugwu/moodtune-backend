CREATE TABLE IF NOT EXISTS song_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    track_id TEXT,
    track_name TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    mood_results JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_song_analyses_user_id_created_at
    ON song_analyses(user_id, created_at DESC);

-- RLS (defense-in-depth; service role key bypasses these, anon key does not)
ALTER TABLE song_analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own song analyses"
    ON song_analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own song analyses"
    ON song_analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own song analyses"
    ON song_analyses FOR DELETE
    USING (auth.uid() = user_id);
