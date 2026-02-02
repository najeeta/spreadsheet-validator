"""Ingestion tools — file upload signaling and CSV/XLSX parsing."""

from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ACCEPTED_FORMATS = [".csv", ".xlsx", ".xls"]


def request_file_upload(tool_context: Any) -> dict:
    """Signal the UI to show a file upload dialog."""
    return {
        "status": "waiting_for_upload",
        "accepted_formats": ACCEPTED_FORMATS,
        "message": "Please upload a CSV or Excel spreadsheet for validation.",
    }


def ingest_file(tool_context: Any, file_path: str) -> dict:
    """Read a CSV or XLSX file from disk and populate session state."""
    import pathlib

    path = pathlib.Path(file_path)

    if path.suffix.lower() not in ACCEPTED_FORMATS:
        return {"status": "error", "message": f"Unsupported file type: {path.suffix}"}

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_path, e)
        return {"status": "error", "message": f"Failed to read file: {e}"}

    records = df.to_dict(orient="records")
    columns = list(df.columns)

    state = tool_context.state
    state["dataframe_records"] = records
    state["dataframe_columns"] = columns
    state["file_path"] = file_path
    state["file_name"] = path.name
    state["status"] = "RUNNING"

    logger.info("Ingested %d rows, %d columns from %s", len(records), len(columns), path.name)
    return {
        "status": "success",
        "row_count": len(records),
        "columns": columns,
        "file_name": path.name,
    }


async def ingest_uploaded_file(tool_context: Any) -> dict:
    """Read a file from the ADK ArtifactService and populate session state."""
    state = tool_context.state
    artifact_name = state.get("uploaded_file")

    if not artifact_name:
        return {"status": "error", "message": "No uploaded file found in state."}

    artifact = await tool_context.load_artifact(filename=artifact_name)
    if artifact is None:
        return {"status": "error", "message": f"Artifact '{artifact_name}' not found."}

    try:
        data = artifact.inline_data.data
        mime = getattr(artifact.inline_data, "mime_type", "")

        if isinstance(data, str):
            data = data.encode()

        if artifact_name.lower().endswith(".csv") or "csv" in mime:
            df = pd.read_csv(io.BytesIO(data))
        else:
            try:
                df = pd.read_excel(io.BytesIO(data))
            except Exception:
                # Fallback: try as CSV
                df = pd.read_csv(io.BytesIO(data))
    except Exception as e:
        logger.error("Failed to parse uploaded artifact %s: %s", artifact_name, e)
        return {"status": "error", "message": f"Failed to parse artifact: {e}"}

    records = df.to_dict(orient="records")
    columns = list(df.columns)

    state["dataframe_records"] = records
    state["dataframe_columns"] = columns
    state["file_name"] = artifact_name
    state["status"] = "RUNNING"

    logger.info("Ingested %d rows from artifact %s", len(records), artifact_name)
    return {
        "status": "success",
        "row_count": len(records),
        "columns": columns,
        "file_name": artifact_name,
    }
