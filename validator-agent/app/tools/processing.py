"""Processing tools — data transformation and Excel artifact packaging."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_COST_CENTER_MAP = {"FIN": "100", "HR": "200", "ENG": "300", "OPS": "400"}

OUTPUT_COLUMNS = {"error_reason", "amount_usd", "cost_center", "approval_required"}


def auto_add_computed_columns(records: list[dict], columns: list[str], state: dict) -> None:
    """Add amount_usd, cost_center, and approval_required to records in-place.

    Called by package_results before building DataFrames to guarantee these
    columns always appear in the final Excel output.
    """
    globals_dict = state.get("globals", {})
    cost_center_map = {**DEFAULT_COST_CENTER_MAP, **(globals_dict.get("cost_center_map") or {})}

    for row in records:
        # amount_usd
        try:
            amount = float(row.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0.0
        try:
            fx_rate = float(row.get("fx_rate", 1.0))
        except (TypeError, ValueError):
            fx_rate = 1.0
        row["amount_usd"] = round(amount * fx_rate, 2)

        # cost_center
        dept = str(row.get("dept", ""))
        row["cost_center"] = cost_center_map.get(dept, "UNMAPPED")

        # approval_required
        row["approval_required"] = "YES" if dept == "FIN" and amount > 50000 else "NO"

    for col in ("amount_usd", "cost_center", "approval_required"):
        if col not in columns:
            columns.append(col)


def transform_data(
    tool_context: Any,
    new_column_name: str,
    default_value: Optional[str] = None,
    expression: Optional[str] = None,
    lookup_field: Optional[str] = None,
    lookup_map: Optional[dict] = None,
    unmapped_value: Optional[str] = "UNMAPPED",
) -> dict:
    """Add a computed column to all records.

    Three modes (checked in order):
    1. **Lookup**: lookup_field + lookup_map — maps values from a source column.
    2. **Expression**: a Python expression evaluated per row.
    3. **Static**: default_value applied to every row.
    """
    # Validate lookup params are paired
    if lookup_map is not None and lookup_field is None:
        return {"status": "error", "message": "lookup_map requires lookup_field."}
    if lookup_field is not None and lookup_map is None:
        return {"status": "error", "message": "lookup_field requires lookup_map."}

    state = tool_context.state
    records = state.get("dataframe_records", [])

    if not records:
        return {"status": "error", "message": "No data loaded to transform."}

    for row in records:
        if lookup_map is not None and lookup_field is not None:
            key = str(row.get(lookup_field, ""))
            row[new_column_name] = lookup_map.get(key, unmapped_value)
        elif expression:
            try:
                row[new_column_name] = eval(
                    expression, {"__builtins__": {}}, {"row": row, "round": round}
                )
            except Exception as e:
                row[new_column_name] = f"ERROR: {e}"
        else:
            row[new_column_name] = default_value

    # Update columns list
    columns = state.get("dataframe_columns", [])
    if new_column_name not in columns:
        columns.append(new_column_name)
        state["dataframe_columns"] = columns

    state["status"] = "TRANSFORMING"

    logger.info("Added column '%s' to %d records", new_column_name, len(records))
    return {
        "status": "success",
        "column_name": new_column_name,
        "row_count": len(records),
    }


def package_results(tool_context: Any) -> dict:
    """Create success.xlsx and errors.xlsx, stored as base64 in state.

    Artifacts are stored in state["artifacts"] as base64-encoded data
    so they survive AgentTool child-session boundaries. The download
    endpoint reads from session state.

    IMPORTANT: This tool will refuse to run if there are pending fixes.
    The user must fix all validation errors before packaging.
    """
    state = tool_context.state
    records = state.get("dataframe_records", [])
    pending_fixes = state.get("pending_fixes", [])
    skipped_fixes = state.get("skipped_fixes", [])
    current_status = state.get("status", "IDLE")

    # Guard: Refuse to package if we're waiting for user fixes or have unresolved pending fixes
    if current_status == "WAITING_FOR_USER" or pending_fixes:
        logger.warning(
            "package_results called while status=%s with %d pending fixes - refusing to proceed",
            current_status,
            len(pending_fixes),
        )
        return {
            "status": "error",
            "action": "STOP - Cannot package results while waiting for user fixes.",
            "message": f"Cannot process results - status is {current_status} with {len(pending_fixes)} validation errors. "
            "Wait for the user to provide fixes, then call validate_data again before packaging.",
            "pending_fixes_count": len(pending_fixes),
        }

    state["status"] = "PACKAGING"

    columns = state.get("dataframe_columns", [])
    auto_add_computed_columns(records, columns, state)
    state["dataframe_columns"] = columns

    # Determine which row indices have errors (from skipped_fixes — user-skipped rows)
    error_indices = {fix["row_index"] for fix in skipped_fixes}

    # Defensive: include any stale remaining_fixes that weren't moved to skipped
    remaining_fixes = state.get("remaining_fixes", [])
    if remaining_fixes:
        logger.warning(
            "package_results found %d stale remaining_fixes — including in error rows",
            len(remaining_fixes),
        )
        for fix in remaining_fixes:
            error_indices.add(fix["row_index"])
            # Also add to skipped_fixes so error_reason is populated
            skipped_fixes.append(fix)
        state["remaining_fixes"] = []

    # Group errors by row_index for error summary
    errors_by_row: dict[int, list[str]] = {}
    for fix in skipped_fixes:
        row_idx = fix["row_index"]
        if row_idx not in errors_by_row:
            errors_by_row[row_idx] = []
        errors_by_row[row_idx].append(fix["error_message"])

    valid_rows = [r for i, r in enumerate(records) if i not in error_indices]
    invalid_rows = []
    for row_idx in sorted(error_indices):
        row = dict(records[row_idx])
        error_summary = "; ".join(errors_by_row.get(row_idx, []))
        row["error_reason"] = error_summary
        invalid_rows.append(row)

    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # success.xlsx
    success_buf = io.BytesIO()
    df_success = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()
    df_success.to_excel(success_buf, index=False)
    success_bytes = success_buf.getvalue()

    # errors.xlsx
    errors_buf = io.BytesIO()
    df_errors = pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame()
    df_errors.to_excel(errors_buf, index=False)
    errors_bytes = errors_buf.getvalue()

    # Store as base64 in state (survives AgentTool child sessions)
    state["artifacts"] = {
        "success.xlsx": {
            "data": base64.b64encode(success_bytes).decode("ascii"),
            "mime_type": xlsx_mime,
        },
        "errors.xlsx": {
            "data": base64.b64encode(errors_bytes).decode("ascii"),
            "mime_type": xlsx_mime,
        },
    }
    state["status"] = "COMPLETED"

    logger.info(
        "Packaged results: %d valid rows, %d invalid rows",
        len(valid_rows),
        len(invalid_rows),
    )
    return {
        "status": "success",
        "valid_count": len(valid_rows),
        "error_count": len(invalid_rows),
        "artifacts": ["success.xlsx", "errors.xlsx"],
    }
