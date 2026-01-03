# Learnings: FastAPI async and blocking calls

**Question:** Why are we using `loop.run_in_executor` around Supabase calls in `app/crud/spotify.py`?

**Explanation:** FastAPI `async def` endpoints run on an event loop (uvicorn). The Supabase Python client is synchronous, so calling it directly in an async route would block the loop and pause other requests. Wrapping the blocking call in `loop.run_in_executor(None, func)` offloads the work to a thread pool and `await` returns when it’s done, keeping the loop responsive. Use this pattern for any blocking I/O inside async endpoints; fully async libraries (e.g., `httpx.AsyncClient`) can be awaited directly without an executor.

