"""Ingestion tools — file upload signaling and CSV/XLSX parsing."""

from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ACCEPTED_FORMATS = [".csv", ".xlsx", ".xls"]


async def ingest_uploaded_file(tool_context: Any, file_name: str, header_row: int = 0) -> dict:
    """Load an uploaded file artifact, parse it, and populate session state.

    Args:
        tool_context: The agent tool context.
        file_name: The name of the file to ingest (must match an uploaded artifact).
        header_row: 0-indexed row number to use as the header (default 0).
    """
    state = tool_context.state
    logger.info("[INGEST] Starting ingestion for file: %s (header_row=%d)", file_name, header_row)
    print(f"[INGEST] Starting ingestion for file: {file_name}")

    try:
        # Use tool_context.load_artifact() — delegates through the runner's
        # invocation context, so it works with both InMemory and GCS backends.
        # This works because /run sets _ag_ui_thread_id at creation time, so
        # ag-ui-adk finds and reuses the same session that /upload saved to.
        artifact = await tool_context.load_artifact(filename=file_name)

        if not artifact or not hasattr(artifact, "inline_data"):
            logger.error("[INGEST] Artifact not found: %s", file_name)
            return {
                "status": "error",
                "message": f"File '{file_name}' not found. Please upload it first.",
            }

        content = artifact.inline_data.data
        logger.info("[INGEST] Loaded artifact %s: %d bytes", file_name, len(content))

        # Parse the file
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        try:
            if ext == "csv":
                df = pd.read_csv(io.BytesIO(content), header=header_row)
            elif ext in ("xlsx", "xls"):
                df = pd.read_excel(io.BytesIO(content), header=header_row)
            else:
                return {"status": "error", "message": f"Unsupported file type: {ext}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to parse file: {e}"}

        # Strip output columns from previous pipeline runs (e.g. re-uploaded errors.xlsx)
        from app.tools.processing import OUTPUT_COLUMNS

        cols_to_drop = [c for c in df.columns if c in OUTPUT_COLUMNS]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        # Normalize data
        df = df.astype(object).where(df.notna(), None)
        records = df.to_dict(orient="records")
        columns = list(df.columns)

        # Compute fingerprints for incremental validation
        from app.utils import compute_all_fingerprints

        fingerprints = compute_all_fingerprints(records)

        # Update state with parsed data
        state["dataframe_records"] = records
        state["dataframe_columns"] = columns
        state["row_fingerprints"] = fingerprints
        state["validated_row_fingerprints"] = {}  # Reset on new ingestion
        state["file_name"] = file_name
        state["status"] = "INGESTING"

        # Reset stale validation state from previous runs
        state["pending_review"] = []
        state["all_errors"] = []
        state["skipped_rows"] = []
        state["waiting_since"] = None

        logger.info("[INGEST] Parsed %d rows, %d columns", len(records), len(columns))
        return {
            "status": "success",
            "file_name": file_name,
            "row_count": len(records),
            "columns": columns,
            "message": "File ingested successfully. Ready for confirmation.",
        }

    except Exception as e:
        logger.error("[INGEST] Unexpected error: %s", e)
        return {"status": "error", "message": f"Unexpected error during ingestion: {e}"}


def confirm_ingestion(tool_context: Any) -> dict:
    """Confirm that file data is loaded and mark pipeline as RUNNING.

    Checks if dataframe_records are present in the state.
    """
    state = tool_context.state
    records = state.get("dataframe_records", [])
    columns = state.get("dataframe_columns", [])
    file_name = state.get("file_name", "Unknown")

    if not records:
        logger.warning("[CONFIRM] No records found in state.")
        return {
            "status": "error",
            "message": "No data found. Please call ingest_uploaded_file first, or upload a file.",
        }

    state["status"] = "RUNNING"
    logger.info("[CONFIRM] Pipeline set to RUNNING. %d rows loaded.", len(records))

    return {
        "status": "success",
        "file_name": file_name,
        "row_count": len(records),
        "columns": columns,
        "message": "Ingestion confirmed. Pipeline is now RUNNING.",
    }


def ingest_file(tool_context: Any, file_path: str) -> dict:
    """Read a CSV or XLSX file from disk and populate session state."""
    import pathlib

    path = pathlib.Path(file_path)

    # Fallback: If file is not on disk, check if it's already in state (e.g. via upload)
    if not path.exists():
        state = tool_context.state
        stored_name = state.get("file_name")
        records = state.get("dataframe_records")
        if stored_name and records and (stored_name == path.name or stored_name == file_path):
            logger.info(
                "File %s not found on disk, but found in state. Using pre-loaded data.", file_path
            )
            state["status"] = "RUNNING"
            return {
                "status": "success",
                "row_count": len(records),
                "columns": state.get("dataframe_columns", []),
                "file_name": stored_name,
            }

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

    # Strip output columns from previous pipeline runs (e.g. re-uploaded errors.xlsx)
    from app.tools.processing import OUTPUT_COLUMNS

    cols_to_drop = [c for c in df.columns if c in OUTPUT_COLUMNS]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    df = df.astype(object).where(df.notna(), None)
    records = df.to_dict(orient="records")
    columns = list(df.columns)

    # Compute fingerprints for incremental validation
    from app.utils import compute_all_fingerprints

    fingerprints = compute_all_fingerprints(records)

    state = tool_context.state
    state["dataframe_records"] = records
    state["dataframe_columns"] = columns
    state["row_fingerprints"] = fingerprints
    state["validated_row_fingerprints"] = {}  # Reset on new ingestion
    state["file_name"] = path.name
    state["status"] = "RUNNING"

    # Reset stale validation state from previous runs
    state["pending_review"] = []
    state["all_errors"] = []
    state["skipped_rows"] = []
    state["waiting_since"] = None

    logger.info("Ingested %d rows, %d columns from %s", len(records), len(columns), path.name)
    return {
        "status": "success",
        "row_count": len(records),
        "columns": columns,
        "file_name": path.name,
    }
