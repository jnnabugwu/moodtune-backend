CREATE TABLE IF NOT EXISTS playlist_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    playlist_id TEXT NOT NULL,
    playlist_name TEXT NOT NULL,
    mood_results JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_playlist_analyses_user_id_created_at
    ON playlist_analyses(user_id, created_at DESC);

-- RLS (defense-in-depth; service role key bypasses these, anon key does not)
ALTER TABLE playlist_analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own playlist analyses"
    ON playlist_analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own playlist analyses"
    ON playlist_analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own playlist analyses"
    ON playlist_analyses FOR DELETE
    USING (auth.uid() = user_id);
