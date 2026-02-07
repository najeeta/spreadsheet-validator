"""ADK lifecycle callbacks for state initialization and prompt injection."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default values for PipelineState keys in session state.
# Mutable defaults are wrapped in lambdas to produce fresh copies.
# NOTE: "status" is intentionally EXCLUDED — it is set explicitly by session
# creation (/run endpoint) and by agent tools.  Including it here risks
# silently resetting the pipeline status to IDLE when AgentTool creates a
# child session whose state copy is missing the key.
_STATE_DEFAULTS: dict[str, Any] = {
    "file_name": None,
    "dataframe_records": lambda: [],
    "dataframe_columns": lambda: [],
    "pending_fixes": lambda: [],
    "skipped_fixes": lambda: [],
    "remaining_fixes": lambda: [],
    "waiting_since": None,
    "total_error_rows": 0,
    "artifacts": lambda: {},
    "row_fingerprints": lambda: [],  # list[str] parallel to dataframe_records
    "validated_row_fingerprints": lambda: {},  # dict[str, bool] fingerprint → was_valid
}

_ROOT_AGENT_NAME = "SpreadsheetValidatorAgent"


def on_before_agent(callback_context: Any) -> None:
    """Idempotent state initialization — fill missing keys with defaults.

    Also injects pending upload data into the session.  This bridges the gap
    when ag-ui-adk syncs frontend state (which may be empty/initial) over
    the backend state that the REST upload endpoint wrote to.
    """
    # Removed upload_store injection.
    # State is now prepopulated by server.py at upload time.
    state = callback_context.state
    agent_name = getattr(callback_context, "agent_name", "unknown")

    # Enhanced logging to debug state flow
    records = state.get("dataframe_records", [])
    columns = state.get("dataframe_columns", [])
    logger.info(
        "on_before_agent [%s]: status=%s, file_name=%s, records=%d, columns=%d",
        agent_name,
        state.get("status", "?"),
        state.get("file_name"),
        len(records) if records else 0,
        len(columns) if columns else 0,
    )

    # Log state for debugging - State object may not have .keys()
    try:
        state_keys = list(state.keys()) if hasattr(state, "keys") else list(dict(state).keys())
        logger.debug("on_before_agent [%s] full state keys: %s", agent_name, state_keys)
    except Exception as e:
        logger.debug("on_before_agent [%s] could not get state keys: %s", agent_name, e)

    initialized = []
    for key, default in _STATE_DEFAULTS.items():
        if key not in state:
            value = default() if callable(default) else default
            state[key] = value
            initialized.append(key)
    if initialized:
        logger.info("on_before_agent [%s] initialized missing keys: %s", agent_name, initialized)


def before_model_modifier(callback_context: Any, llm_request: Any) -> None:
    """Inject a state summary into every agent's system instruction.

    Sub-agents (IngestionAgent, ValidationAgent, etc.) need the state summary
    too — otherwise the LLM cannot see whether dataframe_records is populated
    and may choose the wrong tool (e.g. ingest_file instead of confirm_ingestion).
    """
    state = callback_context.state
    lines = [
        "\n--- Current Pipeline State ---",
        f"status: {state.get('status', 'UNKNOWN')}",
    ]
    if state.get("file_name"):
        lines.append(f"file_name: {state['file_name']}")
    records = state.get("dataframe_records", [])
    if records:
        lines.append(f"row_count: {len(records)}")
    columns = state.get("dataframe_columns", [])
    if columns:
        if len(columns) > 50:
            lines.append(f"columns: {columns[:50]}... (+{len(columns) - 50} more)")
        else:
            lines.append(f"columns: {columns}")
    fixes = state.get("pending_fixes", [])
    if fixes:
        lines.append(f"pending_fixes: {len(fixes)}")
    artifacts = state.get("artifacts", {})
    if artifacts:
        lines.append(f"artifacts: {list(artifacts.keys())}")
    globals_dict = state.get("globals")
    if globals_dict and isinstance(globals_dict, dict):
        cost_map = globals_dict.get("cost_center_map")
        if cost_map:
            lines.append(f"cost_center_map: {cost_map}")
        as_of = globals_dict.get("as_of")
        if as_of:
            lines.append(f"as_of: {as_of}")
    lines.append("--- End Pipeline State ---\n")

    summary = "\n".join(lines)
    existing = llm_request.config.system_instruction or ""
    llm_request.config.system_instruction = existing + summary


def after_model_modifier(callback_context: Any, llm_response: Any) -> None:
    """Log response for debugging. Does not modify the response."""
    logger.debug("after_model_modifier called — no modifications applied")
    return None


def after_tool_callback(
    tool: Any,
    args: dict,
    tool_context: Any,
    tool_response: Any,
) -> None:
    """Log tool execution results and state changes for debugging."""
    tool_name = getattr(tool, "name", str(tool))
    state = tool_context.state

    # Log key state fields after tool execution
    logger.info(
        "[after_tool] Tool '%s' completed. State: status=%s, pending_fixes=%d, validated_fp=%d",
        tool_name,
        state.get("status", "?"),
        len(state.get("pending_fixes", [])),
        len(state.get("validated_row_fingerprints", {})),
    )

    # Check if state has delta (pending changes)
    if hasattr(state, "has_delta") and state.has_delta():
        logger.info("[after_tool] State has pending delta changes")

    return None  # Don't modify result
