"""Pure fix-application functions for session state dicts.

These are the core state-mutation functions used by both the ADK tool wrappers
(app/tools/validation.py) and the REST /answers endpoint (app/server.py).
They operate on plain dicts, not ToolContext.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.utils import compute_row_fingerprint

logger = logging.getLogger(__name__)

FIX_BATCH_SIZE = 5


def _rebatch_fixes(state: dict) -> None:
    """Move next batch from remaining_fixes to pending_fixes if current batch is empty.

    This ensures the user sees the next batch of errors when the current batch is
    fully addressed (all fixes applied or skipped).
    """
    pending = state.get("pending_fixes", [])
    remaining = state.get("remaining_fixes", [])

    if not pending and remaining:
        # Move next batch from remaining to pending
        next_batch = remaining[:FIX_BATCH_SIZE]
        next_remaining = remaining[FIX_BATCH_SIZE:]
        state["pending_fixes"] = next_batch
        state["remaining_fixes"] = next_remaining
        state["status"] = "WAITING_FOR_USER"
        state["waiting_since"] = time.time()
        logger.info("Rebatched fixes: moved %d fixes to pending, %d remain",
                   len(next_batch), len(next_remaining))


def apply_single_fix(state: dict, row_index: int, field: str, new_value: Any) -> dict:
    """Apply a single cell fix to a data record.

    Args:
        state: Session state dict (must contain dataframe_records, pending_fixes, etc.).
        row_index: Zero-based row index.
        field: Column name to update.
        new_value: New value for the cell.

    Returns:
        Result dict with status, row_index, field, old/new values, remaining_fixes count.
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

    # Remove matching pending fix
    old_pending = state.get("pending_fixes", [])
    new_pending = [
        f for f in old_pending if not (f["row_index"] == row_index and f["field"] == field)
    ]
    state["pending_fixes"] = new_pending

    # Try to rebatch if current batch is empty but more fixes remain
    _rebatch_fixes(state)

    # Update status based on what's left
    if not state.get("pending_fixes"):
        state["status"] = "RUNNING"
    else:
        state["status"] = "FIXING"
        state["waiting_since"] = time.time()

    logger.info("Fixed row %d, field '%s': '%s' -> '%s'", row_index, field, old_value, new_value)
    total_remaining = len(new_pending) + len(state.get("remaining_fixes", []))
    return {
        "status": "fixed",
        "row_index": row_index,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "remaining_fixes": total_remaining,
    }


def apply_batch_fixes(state: dict, row_index: int, fixes: dict[str, Any]) -> dict:
    """Apply multiple fixes to one row at once.

    Args:
        state: Session state dict.
        row_index: Zero-based row index.
        fixes: Dict mapping field names to new values.

    Returns:
        Result dict with status, applied changes, remaining_fixes count.
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

    # Remove matching pending fixes for this row + fields
    fix_fields = set(fixes.keys())
    old_pending = state.get("pending_fixes", [])
    new_pending = [
        f for f in old_pending if not (f["row_index"] == row_index and f["field"] in fix_fields)
    ]
    state["pending_fixes"] = new_pending

    # Try to rebatch if current batch is empty but more fixes remain
    _rebatch_fixes(state)

    if not state.get("pending_fixes"):
        state["status"] = "RUNNING"
    else:
        state["status"] = "FIXING"
        state["waiting_since"] = time.time()

    logger.info("Batch fixed row %d: %s", row_index, list(fixes.keys()))
    total_remaining = len(new_pending) + len(state.get("remaining_fixes", []))
    return {
        "status": "fixed",
        "row_index": row_index,
        "applied": applied,
        "remaining_fixes": total_remaining,
    }


def apply_skip_row(state: dict, row_index: int) -> dict:
    """Skip a single row — move its fixes from pending to skipped.

    Args:
        state: Session state dict.
        row_index: Zero-based row index.

    Returns:
        Result dict with status, remaining_fixes count.
    """
    try:
        row_index = int(row_index)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "message": f"Invalid row_index: {row_index}. Must be an integer.",
        }

    old_pending = state.get("pending_fixes", [])
    skipped = state.get("skipped_fixes", [])

    row_fixes = [f for f in old_pending if f["row_index"] == row_index]
    if not row_fixes:
        return {"status": "no_op", "message": f"No pending fixes for row {row_index}."}

    new_pending = [f for f in old_pending if f["row_index"] != row_index]
    skipped.extend(row_fixes)
    state["pending_fixes"] = new_pending
    state["skipped_fixes"] = skipped

    # Mark fingerprint as invalid so state reflects true data quality
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    if row_index < len(fingerprints):
        fp = fingerprints[row_index]
        if fp:
            valid_fp[fp] = False
            state["validated_row_fingerprints"] = valid_fp

    # Try to rebatch if current batch is empty but more fixes remain
    _rebatch_fixes(state)

    if not state.get("pending_fixes"):
        state["status"] = "RUNNING"
    else:
        state["status"] = "FIXING"
        state["waiting_since"] = time.time()

    logger.info("Skipped row %d (%d fixes moved to skipped_fixes)", row_index, len(row_fixes))
    total_remaining = len(new_pending) + len(state.get("remaining_fixes", []))
    return {
        "status": "skipped",
        "row_index": row_index,
        "remaining_fixes": total_remaining,
    }


def apply_skip_all(state: dict) -> dict:
    """Skip ALL remaining pending + remaining fixes.

    Args:
        state: Session state dict.

    Returns:
        Result dict with status and skipped_count.
    """
    pending = state.get("pending_fixes", [])
    remaining = state.get("remaining_fixes", [])
    if not pending and not remaining:
        return {"status": "no_op", "message": "No pending fixes to skip."}

    # Mark all skipped row fingerprints as invalid
    fingerprints = state.get("row_fingerprints", [])
    valid_fp = state.get("validated_row_fingerprints", {})
    skipped_row_indices = {f["row_index"] for f in pending + remaining}
    for row_index in skipped_row_indices:
        if row_index < len(fingerprints):
            fp = fingerprints[row_index]
            if fp:
                valid_fp[fp] = False
    state["validated_row_fingerprints"] = valid_fp

    skipped = state.get("skipped_fixes", [])
    skipped.extend(pending)
    skipped.extend(remaining)
    state["skipped_fixes"] = skipped
    state["pending_fixes"] = []
    state["remaining_fixes"] = []
    state["status"] = "RUNNING"
    state["validation_complete"] = True
    state["waiting_since"] = None

    skipped_count = len(pending) + len(remaining)
    logger.info(
        "Skipped all %d remaining fixes (pending=%d, remaining=%d)",
        skipped_count,
        len(pending),
        len(remaining),
    )
    return {
        "status": "skipped",
        "action": "Proceed directly to process_results. Do NOT re-validate.",
        "skipped_count": skipped_count,
    }
