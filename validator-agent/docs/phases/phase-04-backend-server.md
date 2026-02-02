# Phase 4: Backend Server

Phase 4 creates the FastAPI server with the AG-UI SSE endpoint (via ag-ui-adk) and supplementary REST endpoints for health checks, file upload, session management, artifact download, and user feedback. No monkey-patches, no `render_a2ui` tool.

**Stories:** 4.1
**Depends on:** Phase 3 (root agent and App)
**Quality check:** `cd validator-agent && pytest tests/e2e/ -v`

---

## Story 4.1: FastAPI server with AG-UI SSE endpoint and REST endpoints {#story-4.1}

### Summary

Create the FastAPI server that hosts the AG-UI SSE streaming endpoint at `/agent` and provides REST endpoints for health, session management, file upload, artifact download, and feedback. Uses `InMemorySessionService` and `InMemoryArtifactService` for development. No monkey-patch modules are imported. No `render_a2ui` tool appears anywhere.

### Test (write first)

**File: `tests/e2e/__init__.py`** (empty)

**File: `tests/e2e/test_server.py`**

```python
"""Tests for FastAPI server — Story 4.1."""
import io
import pathlib

import pytest
import httpx

from app.server import fastapi_app


@pytest.fixture
def client():
    """Create an async test client for the FastAPI app."""
    transport = httpx.ASGITransport(app=fastapi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestHealthEndpoint:
    """GET /health returns status healthy."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        async with client as c:
            resp = await c.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestRunEndpoint:
    """POST /run creates a session."""

    @pytest.mark.asyncio
    async def test_create_run(self, client):
        async with client as c:
            resp = await c.post("/run", params={"thread_id": "test-thread-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_create_run_has_thread_id_in_state(self, client):
        async with client as c:
            resp = await c.post("/run", params={"thread_id": "test-thread-2"})
        data = resp.json()
        assert data.get("thread_id") == "test-thread-2"


class TestUploadEndpoint:
    """POST /upload saves file as artifact and updates session state."""

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        async with client as c:
            # First create a session
            run_resp = await c.post("/run", params={"thread_id": "upload-test"})
            session_id = run_resp.json()["session_id"]

            # Upload a CSV
            csv_content = b"employee_id,dept,amount\nEMP001,Engineering,1500"
            files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
            resp = await c.post("/upload", params={"thread_id": "upload-test"}, files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["file_name"] == "test.csv"

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_type(self, client):
        async with client as c:
            run_resp = await c.post("/run", params={"thread_id": "upload-reject-test"})

            files = {"file": ("test.json", io.BytesIO(b'{"a": 1}'), "application/json")}
            resp = await c.post(
                "/upload", params={"thread_id": "upload-reject-test"}, files=files
            )

        assert resp.status_code == 400


class TestRunsEndpoint:
    """GET /runs lists sessions; GET /runs/{id} returns full state."""

    @pytest.mark.asyncio
    async def test_list_runs(self, client):
        async with client as c:
            await c.post("/run", params={"thread_id": "list-test-1"})
            resp = await c.get("/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_run_detail(self, client):
        async with client as c:
            run_resp = await c.post("/run", params={"thread_id": "detail-test"})
            session_id = run_resp.json()["session_id"]
            resp = await c.get(f"/runs/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, client):
        async with client as c:
            resp = await c.get("/runs/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs_strips_heavy_keys(self, client):
        async with client as c:
            await c.post("/run", params={"thread_id": "heavy-test"})
            resp = await c.get("/runs")
        data = resp.json()
        if data:
            run = data[0]
            # Heavy keys should be stripped from listing
            assert "dataframe_records" not in run


class TestArtifactsEndpoint:
    """GET /artifacts/{name} returns artifact or 404."""

    @pytest.mark.asyncio
    async def test_artifact_not_found(self, client):
        async with client as c:
            resp = await c.get("/artifacts/nonexistent.xlsx")
        assert resp.status_code == 404


class TestFeedbackEndpoint:
    """POST /feedback records feedback."""

    @pytest.mark.asyncio
    async def test_feedback_returns_201(self, client):
        async with client as c:
            resp = await c.post(
                "/feedback",
                json={"session_id": "test", "rating": "thumbs_up", "comment": "Good"},
            )
        assert resp.status_code == 201


class TestNoMonkeyPatches:
    """server.py must not import monkey-patch modules."""

    def test_no_monkey_patch_imports(self):
        source = pathlib.Path(__file__).resolve().parents[2] / "app" / "server.py"
        content = source.read_text()
        assert "monkey_patch" not in content.lower()
        assert "render_a2ui" not in content


class TestAgentEndpointExists:
    """/agent endpoint should be registered."""

    @pytest.mark.asyncio
    async def test_agent_endpoint_registered(self, client):
        async with client as c:
            # AG-UI endpoint should exist — a GET may return 405 (method not allowed)
            # or the endpoint may require SSE headers. We just check it's routed.
            resp = await c.post(
                "/agent",
                headers={"Content-Type": "application/json"},
                content="{}",
            )
        # Should not be 404 — endpoint exists
        assert resp.status_code != 404
```

### Implementation

**File: `app/server.py`**

```python
"""FastAPI server with AG-UI SSE endpoint and REST endpoints."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.genai.types import Part

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

from app.agent import adk_app

logger = logging.getLogger(__name__)

# ── Shared services ──────────────────────────────────────────────────────
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

APP_NAME = adk_app.name
USER_ID = "default_user"

# ── FastAPI app ──────────────────────────────────────────────────────────
fastapi_app = FastAPI(title="Spreadsheet Validator", version="0.1.0")

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── AG-UI SSE endpoint ──────────────────────────────────────────────────
adk_agent = ADKAgent.from_app(
    adk_app,
    session_service=session_service,
    artifact_service=artifact_service,
    emit_messages_snapshot=True,
)

add_adk_fastapi_endpoint(fastapi_app, "/agent", adk_agent)

# ── Session tracking (thread_id -> session_id) ──────────────────────────
_thread_to_session: dict[str, str] = {}
_sessions: dict[str, dict[str, Any]] = {}

HEAVY_KEYS = {"dataframe_records", "dataframe_columns", "validation_errors", "pending_fixes"}


# ── REST endpoints ───────────────────────────────────────────────────────
@fastapi_app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@fastapi_app.post("/run")
async def create_run(thread_id: str):
    """Pre-create an ADK session for a given thread_id."""
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"_ag_ui_thread_id": thread_id, "status": "IDLE"},
    )
    session_id = session.id
    _thread_to_session[thread_id] = session_id
    _sessions[session_id] = {
        "session_id": session_id,
        "thread_id": thread_id,
        "status": "IDLE",
    }
    logger.info("Created session %s for thread %s", session_id, thread_id)
    return {"session_id": session_id, "thread_id": thread_id}


@fastapi_app.post("/upload")
async def upload_file(thread_id: str, file: UploadFile = File(...)):
    """Upload a CSV/XLSX file, save as ADK artifact, update session state."""
    # Validate file type
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    # Read file
    content = await file.read()

    # Determine MIME type
    mime_map = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    # Save as ADK artifact
    session_id = _thread_to_session.get(thread_id)
    if session_id:
        artifact = Part.from_data(data=content, mime_type=mime_type)
        await artifact_service.save_artifact(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
            filename=filename,
            artifact=artifact,
        )

        # Update session state
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )
        if session:
            session.state["uploaded_file"] = filename
            session.state["file_name"] = filename
            session.state["status"] = "UPLOADING"

    logger.info("Uploaded %s (%d bytes) for thread %s", filename, len(content), thread_id)
    return {"status": "uploaded", "file_name": filename, "size": len(content)}


@fastapi_app.get("/runs")
async def list_runs():
    """List all sessions with lightweight state (strip heavy keys)."""
    runs = []
    for sid, meta in _sessions.items():
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=sid
        )
        if session:
            light_state = {
                k: v for k, v in session.state.items() if k not in HEAVY_KEYS
            }
            runs.append({
                "session_id": sid,
                "thread_id": meta.get("thread_id"),
                **light_state,
            })
        else:
            runs.append(meta)
    return runs


@fastapi_app.get("/runs/{session_id}")
async def get_run(session_id: str):
    """Get full session state for a run."""
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {
        "session_id": session_id,
        **session.state,
    }


@fastapi_app.get("/artifacts/{name}")
async def get_artifact(name: str):
    """Download an artifact by name."""
    # Search across all sessions
    for sid in _sessions:
        artifact = await artifact_service.load_artifact(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=sid,
            filename=name,
        )
        if artifact is not None:
            data = artifact.inline_data.data
            mime = artifact.inline_data.mime_type or "application/octet-stream"
            return Response(
                content=data,
                media_type=mime,
                headers={"Content-Disposition": f'attachment; filename="{name}"'},
            )
    raise HTTPException(status_code=404, detail=f"Artifact '{name}' not found.")


@fastapi_app.post("/feedback", status_code=201)
async def submit_feedback(feedback: dict):
    """Record user feedback (thumbs up/down with optional comment)."""
    logger.info(
        "Feedback received: session=%s, rating=%s, comment=%s",
        feedback.get("session_id"),
        feedback.get("rating"),
        feedback.get("comment"),
    )
    return {"status": "recorded", **feedback}
```

### Success criteria

- [ ] `GET /health` returns `{'status': 'healthy'}` with 200
- [ ] `POST /run` creates a session with `_ag_ui_thread_id` in state
- [ ] `POST /upload` saves file as ADK artifact and sets `state['uploaded_file']`
- [ ] `POST /upload` rejects non-csv/xlsx files with 400
- [ ] `GET /runs` returns sessions without heavy row-array keys
- [ ] `GET /runs/{id}` returns full session state
- [ ] `GET /runs/{id}` returns 404 for non-existent session
- [ ] `GET /artifacts/{name}` returns 404 for missing artifacts
- [ ] `POST /feedback` records feedback and returns 201
- [ ] `/agent` endpoint exists (AG-UI SSE)
- [ ] No monkey-patch modules imported in `server.py`
- [ ] No `render_a2ui` text appears in `server.py`
- [ ] All tests in `tests/e2e/test_server.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/e2e/test_server.py -v
```

### Commit message

```
feat(server): add FastAPI server with AG-UI SSE and REST endpoints

- AG-UI SSE endpoint at /agent via ag-ui-adk
- REST: /health, /run, /upload, /runs, /artifacts, /feedback
- InMemorySessionService and InMemoryArtifactService for dev
- No monkey-patches, no render_a2ui
```
