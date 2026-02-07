"""FastAPI server with AG-UI SSE endpoint and REST endpoints."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from google.adk.events import Event
from google.adk.runners import Runner
from google.genai.types import Content, Part

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

from app.agent import adk_app
from app.api_models import AnswerRequest, AnswerResponse, CreateRunResponse
from app.fix_utils import apply_batch_fixes, apply_single_fix, apply_skip_all, apply_skip_row
from app.run_manager import run_manager, run_pipeline
from app.services import ENVIRONMENT, artifact_service, session_service

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -- Constants -----------------------------------------------------------------
APP_NAME = adk_app.name
USER_ID = "default_user"

# -- Thread-to-session mapping -------------------------------------------------
# In production, the frontend uses a UUID thread_id (returned by /run).
# Vertex assigns its own session ID. This mapping resolves thread_id → vertex_session_id
# so /upload and /runs/{id} can find the right session.
_thread_to_session: dict[str, str] = {}


def _resolve_session_id(thread_id: str) -> str:
    """Resolve a thread_id to the actual Vertex session ID. No-op in dev."""
    return _thread_to_session.get(thread_id, thread_id)


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
    user_id=USER_ID,
)

add_adk_fastapi_endpoint(fastapi_app, adk_agent, "/agent")

# -- Session tracking ----------------------------------------------------------
HEAVY_KEYS = {
    "dataframe_records",
    "dataframe_columns",
    "pending_fixes",
}


# -- REST endpoints ------------------------------------------------------------
@fastapi_app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@fastapi_app.post("/run")
async def create_run():
    """Create a new ADK session with AG-UI metadata.

    Both environments generate a UUID as the thread_id and set it in state
    at creation time. This ensures ag-ui-adk can find the session later by
    matching ``_ag_ui_thread_id``.

    In production, Vertex assigns the session ID (different from thread_id).
    In development, the thread_id IS the session ID (InMemory accepts it).
    """
    thread_id = str(uuid.uuid4())

    initial_state = {
        "status": "IDLE",
        "_ag_ui_thread_id": thread_id,
        "_ag_ui_app_name": APP_NAME,
        "_ag_ui_user_id": USER_ID,
    }

    if ENVIRONMENT == "production":
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            state=initial_state,
        )
        # Map thread_id → Vertex session ID for /upload and /runs lookups
        _thread_to_session[thread_id] = session.id
        logger.info("[RUN] Created session %s (thread %s)", session.id, thread_id)
    else:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=thread_id,
            state=initial_state,
        )
        logger.info("[RUN] Created session %s", session.id)

    # Always return the thread_id — the frontend uses this for everything
    return {"session_id": thread_id}


@fastapi_app.post("/upload")
async def upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    trigger_message: str | None = Form(None),
):
    """Upload a file and save it as an artifact in the session."""
    filename = file.filename or "uploaded_file"
    content = await file.read()

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    mime_map = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    # Resolve thread_id to actual session ID
    real_session_id = _resolve_session_id(session_id)

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=real_session_id
    )

    if not session:
        if ENVIRONMENT == "production":
            raise HTTPException(
                status_code=404,
                detail=f"Session '{session_id}' not found. Create one via POST /run first.",
            )
        # Dev: fallback — create session on the fly
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
            state={
                "_ag_ui_thread_id": session_id,
                "_ag_ui_app_name": APP_NAME,
                "_ag_ui_user_id": USER_ID,
            },
        )
        logger.info("Created new session %s", session_id)

    # Save file as artifact
    artifact = Part.from_bytes(data=content, mime_type=mime_type)
    await artifact_service.save_artifact(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=real_session_id,
        filename=filename,
        artifact=artifact,
    )

    # Update session state with file_name
    session.state["file_name"] = filename

    # Inject trigger event if provided
    if trigger_message:
        event = Event(
            author="UI_Upload_Action",
            content=Content(parts=[Part(text=trigger_message)]),
        )
        await session_service.append_event(session=session, event=event)

    logger.info("Uploaded %s (%d bytes) for session %s", filename, len(content), real_session_id)
    return {"status": "uploaded", "file_name": filename, "size": len(content)}


@fastapi_app.get("/runs")
async def list_runs():
    """List all sessions with lightweight state (strip heavy keys)."""
    response = await session_service.list_sessions(app_name=APP_NAME, user_id=USER_ID)
    runs = []

    for session in response.sessions:
        light_state = {k: v for k, v in session.state.items() if k not in HEAVY_KEYS}
        runs.append(
            {
                "session_id": session.id,
                **light_state,
            }
        )
    return runs


@fastapi_app.get("/runs/{session_id}")
async def get_run(session_id: str):
    """Get full session state for a run."""
    real_session_id = _resolve_session_id(session_id)
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=real_session_id
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
    sessions_response = await session_service.list_sessions(app_name=APP_NAME, user_id=USER_ID)
    sessions = sessions_response.sessions

    # Check session state for base64-encoded artifacts
    for session in sessions:
        artifact_info = (session.state.get("artifacts") or {}).get(name)
        if isinstance(artifact_info, dict) and "data" in artifact_info:
            data = base64.b64decode(artifact_info["data"])
            mime = artifact_info.get("mime_type", "application/octet-stream")
            return Response(
                content=data,
                media_type=mime,
                headers={"Content-Disposition": f'attachment; filename="{name}"'},
            )

    # Fall back to ADK artifact service
    for session in sessions:
        artifact = await artifact_service.load_artifact(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session.id,
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
    """Record user feedback."""
    logger.info(
        "Feedback received: session=%s, rating=%s, comment=%s",
        feedback.get("session_id"),
        feedback.get("rating"),
        feedback.get("comment"),
    )
    return {"status": "recorded", **feedback}


# -- Async Pipeline endpoints --------------------------------------------------


@fastapi_app.post("/runs", status_code=202, response_model=CreateRunResponse)
async def create_async_run(file: UploadFile = File(...)):
    """Start an async pipeline run with file upload.

    Accepts a CSV/XLSX file, creates a session, saves the file as an artifact,
    and spawns a background task to run the agent pipeline.
    Returns 202 with run_id immediately.
    """
    filename = file.filename or "uploaded_file"
    content = await file.read()

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    mime_map = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    # Create session
    thread_id = str(uuid.uuid4())
    initial_state = {
        "status": "RUNNING",
        "file_name": filename,
        "_ag_ui_thread_id": thread_id,
        "_ag_ui_app_name": APP_NAME,
        "_ag_ui_user_id": USER_ID,
    }

    if ENVIRONMENT == "production":
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            state=initial_state,
        )
        _thread_to_session[thread_id] = session.id
        real_session_id = session.id
    else:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=thread_id,
            state=initial_state,
        )
        real_session_id = session.id

    # Save file as artifact
    artifact = Part.from_bytes(data=content, mime_type=mime_type)
    await artifact_service.save_artifact(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=real_session_id,
        filename=filename,
        artifact=artifact,
    )

    # Register run and spawn background task
    run_ctx = run_manager.create_run(thread_id)

    runner = Runner(
        agent=adk_app.root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )

    run_ctx.task = asyncio.create_task(
        run_pipeline(
            run_ctx=run_ctx,
            runner=runner,
            session_id=real_session_id,
            user_id=USER_ID,
            filename=filename,
        )
    )

    logger.info("[POST /runs] Created async run %s for file %s", thread_id, filename)
    return CreateRunResponse(run_id=thread_id, status="RUNNING")


@fastapi_app.post("/runs/{run_id}/answers", response_model=AnswerResponse)
async def submit_answers(run_id: str, body: AnswerRequest):
    """Submit fixes for a WAITING_FOR_USER run.

    Applies fixes in order: skip_all -> fixes -> row_fixes -> skip_rows.
    If all pending fixes are resolved, signals the background task to resume.
    """
    # Validate run exists
    run_ctx = run_manager.get_run(run_id)
    if not run_ctx:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    # Get session
    real_session_id = _resolve_session_id(run_id)
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=real_session_id
    )
    if not session:
        raise HTTPException(status_code=404, detail=f"Session for run '{run_id}' not found.")

    # Check status
    current_status = session.state.get("status", "")
    if current_status != "WAITING_FOR_USER":
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' is not waiting for user input (status: {current_status}).",
        )

    state = session.state
    applied_count = 0
    skipped_count = 0

    # Apply in order: skip_all first
    if body.skip_all:
        result = apply_skip_all(state)
        if result["status"] == "skipped":
            skipped_count += result["skipped_count"]
    else:
        # Individual cell fixes
        if body.fixes:
            for fix in body.fixes:
                result = apply_single_fix(state, fix.row_index, fix.field, fix.new_value)
                if result["status"] == "fixed":
                    applied_count += 1

        # Batch row fixes
        if body.row_fixes:
            for rf in body.row_fixes:
                result = apply_batch_fixes(state, rf.row_index, rf.fixes)
                if result["status"] == "fixed":
                    applied_count += len(rf.fixes)

        # Skip specific rows
        if body.skip_rows:
            for row_idx in body.skip_rows:
                result = apply_skip_row(state, row_idx)
                if result["status"] == "skipped":
                    skipped_count += 1

    # Check if we should signal the background task to resume
    new_status = state.get("status", "")
    if new_status in ("RUNNING", "FIXING") and new_status != "WAITING_FOR_USER":
        run_manager.signal_resume(run_id)

    pending_count = len(state.get("pending_fixes", []))
    remaining_count = len(state.get("remaining_fixes", []))

    message = f"Applied {applied_count} fixes, skipped {skipped_count} rows."
    if pending_count > 0:
        message += f" {pending_count} pending fixes remain."
    elif new_status == "RUNNING":
        message += " Pipeline resuming."

    return AnswerResponse(
        status=new_status,
        pending_fixes_count=pending_count,
        remaining_fixes_count=remaining_count,
        skipped_count=skipped_count,
        applied_count=applied_count,
        message=message,
    )
