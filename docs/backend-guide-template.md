# Backend task guide — pattern & example

This is the document shape Claude produces for every backend task.
Read the guide to understand what's happening, then paste the prompt at the
bottom into a Claude session opened inside `moodtune-backend/`.

---

## Example task: add a new API endpoint

### What & why

Describe the feature here — one or two sentences on what it does and why it's
being added. Example: "Add a `GET /catalog/search` endpoint that queries the
Jamendo API and returns mood-tagged tracks matching a search term."

### Files to touch

| File | What changes |
|---|---|
| `app/schemas/<feature>.py` | New Pydantic request/response models |
| `app/services/<feature>_service.py` | Business logic — the actual work |
| `app/api/v1/<feature>.py` | Route handler — calls the service, returns the response |
| `app/api/v1/api.py` | Register the new router (one line) |
| `tests/test_<feature>.py` | pytest tests for the endpoint |

### Step-by-step walkthrough

**Step 1 — Schema first**

Define what goes in and what comes out. FastAPI validates request bodies and
serialises responses automatically using these models.

```python
# app/schemas/catalog.py
from pydantic import BaseModel

class CatalogSearchRequest(BaseModel):
    query: str
    mood: str | None = None
    limit: int = 20

class CatalogTrack(BaseModel):
    id: str
    title: str
    artist: str
    mood_tags: list[str]

class CatalogSearchResponse(BaseModel):
    tracks: list[CatalogTrack]
    total: int
```

**Step 2 — Service function**

All logic lives here. The router should not contain business logic — it just
calls the service and hands back the result.

```python
# app/services/catalog_service.py
import httpx
from app.schemas.catalog import CatalogSearchResponse

async def search_catalog(query: str, mood: str | None, limit: int) -> CatalogSearchResponse:
    # Call external API, transform results, return typed response
    ...
```

**Step 3 — Route handler**

Thin wrapper. Validates input (Pydantic does this), calls the service, returns output.

```python
# app/api/v1/catalog.py
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_current_user
from app.schemas.catalog import CatalogSearchResponse
from app.services.catalog_service import search_catalog

router = APIRouter()

@router.get("/search", response_model=CatalogSearchResponse)
async def catalog_search(
    q: str = Query(..., description="Search term"),
    mood: str | None = Query(None),
    limit: int = Query(20, le=100),
    _user: dict = Depends(get_current_user),
):
    return await search_catalog(query=q, mood=mood, limit=limit)
```

**Step 4 — Register the router**

```python
# app/api/v1/api.py — add one line
from app.api.v1 import catalog  # already imported if file exists

api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
```

**Step 5 — Tests**

```python
# tests/test_catalog.py
import pytest
from httpx import AsyncClient

async def test_catalog_search_returns_tracks(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/catalog/search?q=happy", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "tracks" in data

async def test_catalog_search_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/catalog/search?q=happy")
    assert response.status_code == 401
```

---

## Prompt

Copy everything below the line and paste into a Claude session inside `moodtune-backend/`.
Replace the bracketed sections with your specifics.

---

```
I need to add a new endpoint to the MoodTune FastAPI backend.

Project structure:
- Routers: app/api/v1/<feature>.py — registered in app/api/v1/api.py
- Schemas (Pydantic models): app/schemas/<feature>.py
- Services (business logic): app/services/<feature>_service.py
- Auth dependency: get_current_user from app/api/deps.py — returns dict with "id" and "email"
- Tests: tests/ using pytest + httpx AsyncClient

What I want to build:
[DESCRIBE THE ENDPOINT: HTTP method, path, purpose, request body or query params, response shape]

External dependencies (if any):
[e.g. "Call the Jamendo API at https://api.jamendo.com/v3.0/tracks with client_id from env"]

Please:
1. Write the Pydantic schema in app/schemas/<feature>.py
2. Write the service function in app/services/<feature>_service.py
3. Write the route handler in app/api/v1/<feature>.py using Depends(get_current_user)
4. Show the one-line addition needed in app/api/v1/api.py
5. Write pytest tests covering the happy path and a 401 unauthenticated case
6. Show full file contents for every file you create or modify

Use async def throughout. Raise HTTPException for errors. Pydantic v2 style (ConfigDict, not class Config).
```
