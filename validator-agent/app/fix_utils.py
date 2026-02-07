"""Pure fix-application functions for session state dicts.

These are the core state-mutation functions used by both the ADK tool wrappers
(app/tools/validation.py) and the REST /answers endpoint (app/server.py).
They operate on plain dicts, not ToolContext.

Pop-based review queue: `pending_review` is the current batch of errors
awaiting user review. Fix/skip always *pop* from the queue; re-validation
catches anything that wasn't actually fixed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.utils import compute_row_fingerprint

logger = logging.getLogger(__name__)

FIX_BATCH_SIZE = 5


def _pop_from_review(state: dict, row_index: int) -> str:
    """Remove all errors for row_index from pending_review.

    Returns:
        "REVALIDATE" if queue is now empty (sets RUNNING).
        "WAIT_FOR_MORE_FIXES" if items remain (sets WAITING_FOR_USER).
    """
    pending = state.get("pending_review", [])
    state["pending_review"] = [e for e in pending if e["row_index"] != row_index]

    if not state["pending_review"]:
        state["status"] = "RUNNING"
        state["waiting_since"] = None
        return "REVALIDATE"

    state["status"] = "WAITING_FOR_USER"
    state["waiting_since"] = time.time()
    return "WAIT_FOR_MORE_FIXES"


def apply_single_fix(state: dict, row_index: int, field: str, new_value: Any) -> dict:
    """Apply a single cell fix to a data record.

    Args:
        state: Session state dict (must contain dataframe_records, etc.).
        row_index: Zero-based row index.
        field: Column name to update.
        new_value: New value for the cell.

    Returns:
        Result dict with status, row_index, field, old/new values, action.
    """
    try:
        row_index = int(row_index)
    except (TypeError, ValueError):
        logger.error("Invalid row_index type: %s (%s)", row_index, type(row_index))
        return {
            "status": "error",
            "message": f"Invalid row_index: {row_index}. Must be an integer.",
        }

    records = state.get("dataframe_records", [])

    if row_index < 0 or row_index >= len(records):
        return {"status": "error", "message": f"Row index {row_index} out of range."}

    old_value = records[row_index].get(field)

    # Get old fingerprint before mutation
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    old_fp = fingerprints[row_index] if row_index < len(fingerprints) else None

    # Apply the fix
    records[row_index][field] = new_value
    state["dataframe_records"] = records

    # Recompute fingerprint for the modified row
    new_fp = compute_row_fingerprint(records[row_index])
    if row_index < len(fingerprints):
        fingerprints[row_index] = new_fp
        state["row_fingerprints"] = fingerprints

    # Remove old fingerprint from valid cache (forces revalidation)
    if old_fp and old_fp in valid_fp:
        del valid_fp[old_fp]
    state["validated_row_fingerprints"] = valid_fp

    # Pop row from review queue
    action = _pop_from_review(state, row_index)

    logger.info("Fixed row %d, field '%s': '%s' -> '%s'", row_index, field, old_value, new_value)
    return {
        "status": "fixed",
        "row_index": row_index,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "remaining_fixes": len(state.get("pending_review", [])),
        "action": action,
    }


def apply_batch_fixes(state: dict, row_index: int, fixes: dict[str, Any]) -> dict:
    """Apply multiple fixes to one row at once.

    Args:
        state: Session state dict.
        row_index: Zero-based row index.
        fixes: Dict mapping field names to new values.

    Returns:
        Result dict with status, applied changes, action.
    """
    try:
        row_index = int(row_index)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "message": f"Invalid row_index: {row_index}. Must be an integer.",
        }

    if not isinstance(fixes, dict) or not fixes:
        return {"status": "error", "message": "fixes must be a non-empty dict of field->value."}

    records = state.get("dataframe_records", [])

    if row_index < 0 or row_index >= len(records):
        return {"status": "error", "message": f"Row index {row_index} out of range."}

    # Get old fingerprint before mutation
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    old_fp = fingerprints[row_index] if row_index < len(fingerprints) else None

    # Apply all fixes
    applied = {}
    for field, new_value in fixes.items():
        old_value = records[row_index].get(field)
        records[row_index][field] = new_value
        applied[field] = {"old": old_value, "new": new_value}

    state["dataframe_records"] = records

    # Recompute fingerprint
    new_fp = compute_row_fingerprint(records[row_index])
    if row_index < len(fingerprints):
        fingerprints[row_index] = new_fp
        state["row_fingerprints"] = fingerprints

    # Remove old fingerprint from valid cache
    if old_fp and old_fp in valid_fp:
        del valid_fp[old_fp]
    state["validated_row_fingerprints"] = valid_fp

    # Pop row from review queue
    action = _pop_from_review(state, row_index)

    logger.info("Batch fixed row %d: %s", row_index, list(fixes.keys()))
    return {
        "status": "fixed",
        "row_index": row_index,
        "applied": applied,
        "remaining_fixes": len(state.get("pending_review", [])),
        "action": action,
    }


def apply_skip_row(state: dict, row_index: int) -> dict:
    """Skip a single row — add it to skipped_rows.

    Args:
        state: Session state dict.
        row_index: Zero-based row index.

    Returns:
        Result dict with status, action.
    """
    try:
        row_index = int(row_index)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "message": f"Invalid row_index: {row_index}. Must be an integer.",
        }

    # Check if row has any active errors
    all_errors = state.get("all_errors", [])
    row_has_errors = any(e["row_index"] == row_index for e in all_errors)
    if not row_has_errors:
        return {"status": "no_op", "message": f"No pending fixes for row {row_index}."}

    # Add to skipped_rows (deduplicated)
    skipped = state.get("skipped_rows", [])
    if row_index not in skipped:
        skipped.append(row_index)
        state["skipped_rows"] = skipped

    # Mark fingerprint as invalid so state reflects true data quality
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    if row_index < len(fingerprints):
        fp = fingerprints[row_index]
        if fp:
            valid_fp[fp] = False
            state["validated_row_fingerprints"] = valid_fp

    # Pop row from review queue
    action = _pop_from_review(state, row_index)

    logger.info("Skipped row %d", row_index)
    return {
        "status": "skipped",
        "row_index": row_index,
        "remaining_fixes": len(state.get("pending_review", [])),
        "action": action,
    }


def apply_skip_all(state: dict) -> dict:
    """Skip ALL remaining active errors.

    Args:
        state: Session state dict.

    Returns:
        Result dict with status and skipped_count.
    """
    all_errors = state.get("all_errors", [])
    skipped = set(state.get("skipped_rows", []))
    records = state.get("dataframe_records", [])

    # Find all row indices with active (unfixed, unskipped) errors
    active_row_indices: set[int] = set()
    for err in all_errors:
        row_idx = err["row_index"]
        if row_idx in skipped:
            continue
        if row_idx < len(records):
            current_val = str(records[row_idx].get(err["field"], ""))
            if current_val != err["current_value"]:
                continue
        active_row_indices.add(row_idx)

    if not active_row_indices:
        return {"status": "no_op", "message": "No pending fixes to skip."}

    # Mark all skipped row fingerprints as invalid
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    for row_index in active_row_indices:
        if row_index < len(fingerprints):
            fp = fingerprints[row_index]
            if fp:
                valid_fp[fp] = False
    state["validated_row_fingerprints"] = valid_fp

    # Add all active error rows to skipped_rows
    skipped_list = state.get("skipped_rows", [])
    for row_idx in active_row_indices:
        if row_idx not in skipped_list:
            skipped_list.append(row_idx)
    state["skipped_rows"] = skipped_list

    state["pending_review"] = []
    state["status"] = "RUNNING"
    state["waiting_since"] = None

    skipped_count = len(active_row_indices)
    logger.info("Skipped all %d remaining error rows", skipped_count)
    return {
        "status": "skipped",
        "action": "Proceed directly to process_results. Do NOT re-validate.",
        "skipped_count": skipped_count,
    }
