-- TestFlight waitlist from getmoodtune.com. The site inserts with the public
-- anon key; nothing can read, change or delete rows through the API. View the
-- list in the Supabase dashboard (Table Editor > beta_signups), invite people
-- in App Store Connect by hand, then set invited_at.
--
-- PRIVACY: an email address and where the signup came from, nothing else.
-- Delete a row when someone asks (privacy@getmoodtune.com).
--
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS beta_signups (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email      text NOT NULL,
  -- utm_source from the landing-page URL, e.g. "linkedin"; else "website".
  source     text NOT NULL DEFAULT 'website',
  created_at timestamptz NOT NULL DEFAULT now(),
  invited_at timestamptz,
  CONSTRAINT beta_signups_email_unique UNIQUE (email),
  CONSTRAINT beta_signups_email_format CHECK (
    email = lower(email)
    AND char_length(email) <= 254
    AND email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
  ),
  CONSTRAINT beta_signups_source_format CHECK (source ~ '^[a-z0-9_-]{1,40}$')
);

ALTER TABLE beta_signups ENABLE ROW LEVEL SECURITY;

-- Visitors may add a row and nothing else: there is no SELECT, UPDATE or
-- DELETE policy, and they can only set email and source.
DROP POLICY IF EXISTS beta_signups_insert ON beta_signups;
CREATE POLICY beta_signups_insert ON beta_signups
  FOR INSERT TO anon, authenticated
  WITH CHECK (true);

REVOKE ALL ON beta_signups FROM anon, authenticated;
GRANT INSERT (email, source) ON beta_signups TO anon, authenticated;
