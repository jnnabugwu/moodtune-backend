-- One row per analysis a user viewed: the backend (librosa) mood next to the
-- on-device (YAMNet) mood, what the app showed, and the user's optional
-- "Does this feel right?" answer. Feeds classifier training (ROADMAP OD-7)
-- and confidence recalibration.
--
-- PRIVACY: never add filenames, titles, artists or audio to this table.
-- Rows hold only mood labels, model outputs and coarse device context.
CREATE TABLE IF NOT EXISTS mood_observations (
    -- Client-generated so the app can PATCH feedback without a round trip.
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Guests are allowed; keep the observation if the account is deleted.
    user_id UUID NULL REFERENCES auth.users(id) ON DELETE SET NULL,

    source TEXT NOT NULL CHECK (source IN ('upload', 'catalog')),
    analysis_id TEXT NULL,

    -- Backend label: happy | energetic | calm | angry | sad
    backend_mood TEXT NOT NULL,

    -- On-device (YAMNet) result. NULL mood + error text when it failed.
    on_device_mood TEXT NULL,
    on_device_tags JSONB NOT NULL DEFAULT '[]',
    on_device_probabilities JSONB NULL,
    on_device_latency_ms INTEGER NULL,
    on_device_error TEXT NULL,

    -- What the results screen showed and which model it came from.
    displayed_mood TEXT NOT NULL,
    displayed_source TEXT NOT NULL
        CHECK (displayed_source IN ('on_device', 'backend')),

    -- User feedback (NULL until answered).
    agrees BOOLEAN NULL,
    user_mood TEXT NULL
        CHECK (user_mood IN ('upbeat', 'serene', 'charged', 'reflective')),
    feedback_at TIMESTAMPTZ NULL,

    -- Coarse device context for slicing accuracy by platform/model/version.
    platform TEXT,
    os_version TEXT,
    device_model TEXT,
    app_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_mood_observations_created_at
    ON mood_observations(created_at DESC);

-- RLS on with NO policies: anon/authenticated keys can neither read nor
-- write. Only the backend's service role key (which bypasses RLS) touches
-- this table.
ALTER TABLE mood_observations ENABLE ROW LEVEL SECURITY;
