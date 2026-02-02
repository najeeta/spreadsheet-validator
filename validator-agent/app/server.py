"""FastAPI server with AG-UI SSE endpoint and REST endpoints."""

from __future__ import annotations

import logging
import os
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

# -- Shared services -----------------------------------------------------------
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

APP_NAME = adk_app.name
USER_ID = "default_user"

# -- FastAPI app ---------------------------------------------------------------
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

# -- AG-UI SSE endpoint --------------------------------------------------------
adk_agent = ADKAgent.from_app(
    adk_app,
    session_service=session_service,
    artifact_service=artifact_service,
    emit_messages_snapshot=True,
)

add_adk_fastapi_endpoint(fastapi_app, adk_agent, "/agent")

# -- Session tracking (thread_id -> session_id) --------------------------------
_thread_to_session: dict[str, str] = {}
_sessions: dict[str, dict[str, Any]] = {}

HEAVY_KEYS = {
    "dataframe_records",
    "dataframe_columns",
    "validation_errors",
    "pending_fixes",
}


# -- REST endpoints ------------------------------------------------------------
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
        artifact = Part.from_bytes(data=content, mime_type=mime_type)
        await artifact_service.save_artifact(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
            filename=filename,
            artifact=artifact,
        )

        # Update session state on the stored session directly.
        # InMemorySessionService.get_session() returns a deep copy,
        # so we must access the internal sessions dict to persist changes.
        stored = session_service.sessions.get(APP_NAME, {}).get(USER_ID, {}).get(session_id)
        if stored:
            stored.state["uploaded_file"] = filename
            stored.state["file_name"] = filename
            stored.state["status"] = "UPLOADING"

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
            light_state = {k: v for k, v in session.state.items() if k not in HEAVY_KEYS}
            runs.append(
                {
                    "session_id": sid,
                    "thread_id": meta.get("thread_id"),
                    **light_state,
                }
            )
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
