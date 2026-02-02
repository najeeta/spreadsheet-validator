"""Processing tools — data transformation and Excel artifact packaging."""

from __future__ import annotations

import io
import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def transform_data(
    tool_context: Any,
    new_column_name: str,
    default_value: Optional[str] = None,
    expression: Optional[str] = None,
) -> dict:
    """Add a computed column to all records.

    Supports either a static default_value or a Python expression
    evaluated with {'row': row} context for each record.
    """
    state = tool_context.state
    records = state.get("dataframe_records", [])

    if not records:
        return {"status": "error", "message": "No data loaded to transform."}

    for row in records:
        if expression:
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


async def package_results(tool_context: Any) -> dict:
    """Create success.xlsx and errors.xlsx artifacts from validated data."""
    state = tool_context.state
    records = state.get("dataframe_records", [])
    validation_errors = state.get("validation_errors", [])

    state["status"] = "PACKAGING"

    # Determine which row indices have errors
    error_indices = {e["row_index"] for e in validation_errors}

    valid_rows = [r for i, r in enumerate(records) if i not in error_indices]
    invalid_rows = []
    for err_entry in validation_errors:
        row = dict(err_entry.get("row_data", records[err_entry["row_index"]]))
        error_summary = "; ".join(e["error"] for e in err_entry["errors"])
        row["_errors"] = error_summary
        invalid_rows.append(row)

    # Create Excel artifacts
    from google.genai.types import Part

    # success.xlsx
    success_buf = io.BytesIO()
    df_success = pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()
    df_success.to_excel(success_buf, index=False)
    success_bytes = success_buf.getvalue()

    success_artifact = Part.from_bytes(
        data=success_bytes,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    await tool_context.save_artifact(filename="success.xlsx", artifact=success_artifact)

    # errors.xlsx
    errors_buf = io.BytesIO()
    df_errors = pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame()
    df_errors.to_excel(errors_buf, index=False)
    errors_bytes = errors_buf.getvalue()

    errors_artifact = Part.from_bytes(
        data=errors_bytes,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    await tool_context.save_artifact(filename="errors.xlsx", artifact=errors_artifact)

    # Update state
    state["artifacts"] = {
        "success.xlsx": "success.xlsx",
        "errors.xlsx": "errors.xlsx",
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
