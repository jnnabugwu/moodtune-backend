-- State store for Spotify OAuth (10 minute TTL recommended)
CREATE TABLE IF NOT EXISTS spotify_oauth_states (
    state TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Optional index to speed up expiry checks
CREATE INDEX IF NOT EXISTS idx_spotify_oauth_states_expires_at
    ON spotify_oauth_states(expires_at DESC);

