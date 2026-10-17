"""Keep the test suite hermetic.

Several CRUD modules build a Supabase client at import time, so without this
the suite either crashes on collection (no env file, as in CI) or quietly
connects to the real dev project (dev.env present, as on a laptop). These
values override any env file because pydantic-settings ranks process env vars
above it. They must be set before anything imports `app`.
"""

import os

_TEST_ENV = {
    # Stay on the dev env file mapping; an unknown ENVIRONMENT falls back to
    # the production .env.
    "ENVIRONMENT": "development",
    # Nothing listens on the discard port, so an unmocked call fails fast
    # instead of reaching a real project.
    "SUPABASE_URL": "http://127.0.0.1:9",
    # supabase-py only checks that keys are JWT-shaped.
    "SUPABASE_KEY": "test-anon.not-a.real-jwt",
    "SUPABASE_SERVICE_KEY": "test-service.not-a.real-jwt",
    "SPOTIFY_CLIENT_ID": "test-client-id",
    "SPOTIFY_CLIENT_SECRET": "test-client-secret",
    "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:9/spotify/callback",
    "SENTRY_ENABLE": "false",
    "SENTRY_DSN_BACKEND": "",
}

os.environ.update(_TEST_ENV)
