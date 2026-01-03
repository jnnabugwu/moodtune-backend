# MoodTune Backend (FastAPI)

Uses Supabase Postgres as the database, deployed on Railway.

## Environment variables
Copy `env.sample` to `.env` (Railway variables) and fill in:
- `SUPABASE_URL`, `SUPABASE_KEY` (anon), `SUPABASE_SERVICE_KEY` (service role)
- `SECRET_KEY`, `ALGORITHM`, token expiry values
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, optional `SPOTIFY_APP_REDIRECT_URI`
- `BACKEND_CORS_ORIGINS` — comma-separated list of allowed origins
- `ENVIRONMENT`, `DEBUG`

## Railway setup
- Monorepo root: `moodtune-backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

## Supabase notes
- Keep `+asyncpg` in `DATABASE_URL` for SQLAlchemy async.
- Use the service role key in the backend if RLS is enabled on your tables.
- Ensure the Supabase project allows connections from Railway (no IP allowlist or add Railway egress IPs).

## Running locally
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

