"""ADK lifecycle callbacks for state initialization and prompt injection."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default values for PipelineState keys in session state.
# Mutable defaults are wrapped in lambdas to produce fresh copies.
_STATE_DEFAULTS: dict[str, Any] = {
    "status": "IDLE",
    "active_run_id": None,
    "file_path": None,
    "file_name": None,
    "uploaded_file": None,
    "dataframe_records": lambda: [],
    "dataframe_columns": lambda: [],
    "validation_errors": lambda: [],
    "validation_complete": False,
    "pending_fixes": lambda: [],
    "artifacts": lambda: {},
    "as_of": None,
    "usd_rounding": "cents",
    "cost_center_map": lambda: {},
}

_ROOT_AGENT_NAME = "SpreadsheetValidatorAgent"


def on_before_agent(callback_context: Any) -> None:
    """Idempotent state initialization — fill missing keys with defaults."""
    state = callback_context.state
    initialized = []
    for key, default in _STATE_DEFAULTS.items():
        if key not in state:
            value = default() if callable(default) else default
            state[key] = value
            initialized.append(key)
    if initialized:
        logger.debug("Initialized state keys: %s", initialized)


def before_model_modifier(callback_context: Any, llm_request: Any) -> None:
    """Inject a state summary into the root agent's system instruction."""
    if callback_context.agent_name != _ROOT_AGENT_NAME:
        return

    state = callback_context.state
    lines = [
        "\n--- Current Pipeline State ---",
        f"status: {state.get('status', 'IDLE')}",
    ]
    if state.get("file_name"):
        lines.append(f"file_name: {state['file_name']}")
    records = state.get("dataframe_records", [])
    if records:
        lines.append(f"row_count: {len(records)}")
    columns = state.get("dataframe_columns", [])
    if columns:
        lines.append(f"columns: {columns}")
    errors = state.get("validation_errors", [])
    if errors:
        lines.append(f"error_count: {len(errors)}")
    fixes = state.get("pending_fixes", [])
    if fixes:
        lines.append(f"pending_fixes: {len(fixes)}")
    artifacts = state.get("artifacts", {})
    if artifacts:
        lines.append(f"artifacts: {list(artifacts.keys())}")
    if state.get("as_of"):
        lines.append(f"as_of: {state['as_of']}")
    if state.get("usd_rounding"):
        lines.append(f"usd_rounding: {state['usd_rounding']}")
    lines.append("--- End Pipeline State ---\n")

    summary = "\n".join(lines)
    existing = llm_request.config.system_instruction or ""
    llm_request.config.system_instruction = existing + summary


def after_model_modifier(callback_context: Any, llm_response: Any) -> None:
    """Log response for debugging. Does not modify the response."""
    logger.debug("after_model_modifier called — no modifications applied")
    return None
