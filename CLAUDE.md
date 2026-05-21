# CLAUDE.md — MoodTune Backend

This file provides guidance to Claude Code when working in the `moodtune-backend/` directory.

## What this is

FastAPI Python backend for MoodTune. Handles mood analysis (via librosa), Spotify OAuth,
audio file uploads, and catalog search. Deployed on Railway. Supabase Postgres is the
database, accessed via the Supabase Python client (no SQLAlchemy).

## Commands

```sh
# Run locally
uvicorn app.main:app --reload

# Run with env vars
source dev.env && uvicorn app.main:app --reload

# Tests
pytest tests/ -v

# Single test
pytest tests/test_analysis.py -v
```

## Project structure

```
app/
├── main.py              # Creates FastAPI app, mounts middleware, includes api_router
├── api/
│   ├── deps.py          # get_current_user — Supabase JWT dependency
│   └── v1/
│       ├── api.py       # Aggregates all routers — add new ones here
│       ├── analysis.py
│       ├── audio_upload.py
│       ├── catalog.py
│       ├── song_analysis.py
│       ├── spotify.py
│       └── ...
├── schemas/             # Pydantic request/response models
├── services/            # Business logic (called by routers, no HTTP knowledge)
├── models/              # DB model helpers
└── core/
    ├── config.py        # Settings (reads from env)
    └── supabase.py      # Supabase client factory
tests/                   # pytest tests
docs/                    # Teaching guides and implementation prompts
```

## Patterns

### Adding a new endpoint — always follow this order

1. **Schema** — define request/response Pydantic models in `app/schemas/<feature>.py`
2. **Service** — write business logic in `app/services/<feature>_service.py`
3. **Router** — add the route in `app/api/v1/<feature>.py`, call the service
4. **Register** — add `api_router.include_router(...)` in `app/api/v1/api.py`
5. **Test** — write a pytest test in `tests/`

### Auth

Protected routes use `Depends(get_current_user)` from `app/api/deps.py`:

```python
from app.api.deps import get_current_user

@router.get("/me")
async def get_profile(user: dict = Depends(get_current_user)):
    user_id = user["id"]
```

### Error handling

```python
from fastapi import HTTPException, status

raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
```

### Async everywhere

All route handlers and service functions use `async def`. Await all I/O.

### Pydantic v2

```python
from pydantic import BaseModel, ConfigDict

class MyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
```

---

## Teaching rule — how to handle backend tasks

When asked to implement any new feature or endpoint:

1. **Create a teaching document** in `docs/` named `YYYYMMDD_<feature-slug>.md`
2. **Explain the task** — what it does, which files it touches, and why each piece exists
3. **Write a ready-to-use prompt** at the bottom so the developer can implement it themselves
4. **Do not write the implementation code** — write the guide and the prompt, then stop

This applies to every backend task, even small ones. The document is the deliverable.
