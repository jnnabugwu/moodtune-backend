-- Stored Spotify OAuth tokens, one row per user.
--
-- INFERRED FROM CODE, NOT DUMPED FROM THE LIVE PROJECT. This table was created
-- by hand in Supabase before db/ existed. The columns below are what the code
-- reads and writes (app/crud/spotify.py, app/services/spotify_api.py,
-- app/schemas/spotify.py); types, defaults and constraints are best guesses.
-- Before relying on this file, compare it with the live table:
--
--   SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--   WHERE table_schema = 'public' AND table_name = 'spotify_connections'
--   ORDER BY ordinal_position;
--
--   SELECT conname, pg_get_constraintdef(oid)
--   FROM pg_constraint
--   WHERE conrelid = 'public.spotify_connections'::regclass;
--
-- FK CASCADE IS UNVERIFIED. DELETE /account (app/services/account_service.py)
-- deletes this user's row explicitly before deleting the auth user, so account
-- deletion does not depend on it. If the live user_id FK is missing or is not
-- ON DELETE CASCADE, this migration (NOT applied by this file) fixes it; the
-- constraint name must match the one the query above returns:
--
--   ALTER TABLE spotify_connections
--       DROP CONSTRAINT spotify_connections_user_id_fkey,
--       ADD CONSTRAINT spotify_connections_user_id_fkey
--           FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
CREATE TABLE IF NOT EXISTS spotify_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- One connection per user: the code reads it with .maybe_single().
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    spotify_user_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Not set on insert; the app writes it on every token refresh.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
