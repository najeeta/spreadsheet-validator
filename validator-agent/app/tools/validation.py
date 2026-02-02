"""Validation tools — 7 business rules and fix lifecycle management."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

VALID_DEPARTMENTS = {
    "Engineering",
    "Marketing",
    "Sales",
    "Finance",
    "HR",
    "Operations",
    "Legal",
    "Support",
}

VALID_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CAD",
    "AUD",
    "CHF",
    "CNY",
    "INR",
    "MXN",
    "BRL",
    "KRW",
    "SEK",
    "NOK",
    "DKK",
    "NZD",
    "SGD",
    "HKD",
    "TRY",
    "ZAR",
}

EMPLOYEE_ID_PATTERN = re.compile(r"^EMP\d{3,}$")


def validate_data(tool_context: Any, as_of_date: Optional[str] = None) -> dict:
    """Validate all records against 7 business rules."""
    state = tool_context.state
    records = state.get("dataframe_records", [])

    if not records:
        return {"status": "error", "message": "No data loaded to validate."}

    # Determine the reference date for future-date checks
    if as_of_date:
        try:
            ref_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        except ValueError:
            ref_date = date.today()
    else:
        ref_date = date.today()

    if as_of_date:
        state["as_of"] = as_of_date

    errors: list[dict] = []
    seen_ids: dict[str, int] = {}

    for idx, row in enumerate(records):
        row_errors: list[dict] = []

        # Rule 1a: employee_id format
        emp_id = str(row.get("employee_id", ""))
        if not EMPLOYEE_ID_PATTERN.match(emp_id):
            row_errors.append(
                {
                    "field": "employee_id",
                    "error": f"Invalid employee_id format: '{emp_id}'. Must match EMP followed by 3+ digits.",
                }
            )

        # Rule 1b: employee_id uniqueness
        if emp_id in seen_ids:
            row_errors.append(
                {
                    "field": "employee_id",
                    "error": f"Duplicate employee_id '{emp_id}' — also at row {seen_ids[emp_id]}.",
                }
            )
        seen_ids[emp_id] = idx

        # Rule 2: department enum
        dept = str(row.get("dept", ""))
        if dept not in VALID_DEPARTMENTS:
            row_errors.append(
                {
                    "field": "dept",
                    "error": f"Invalid department '{dept}'. Must be one of: {sorted(VALID_DEPARTMENTS)}.",
                }
            )

        # Rule 3: amount range
        try:
            amount = float(row.get("amount", 0))
            if amount <= 0 or amount > 100000:
                row_errors.append(
                    {
                        "field": "amount",
                        "error": f"Amount {amount} out of range. Must be > 0 and <= 100,000.",
                    }
                )
        except (TypeError, ValueError):
            row_errors.append(
                {
                    "field": "amount",
                    "error": f"Invalid amount value: '{row.get('amount')}'.",
                }
            )

        # Rule 4: currency enum
        currency = str(row.get("currency", ""))
        if currency not in VALID_CURRENCIES:
            row_errors.append(
                {
                    "field": "currency",
                    "error": f"Invalid currency '{currency}'. Must be a valid ISO 4217 code.",
                }
            )

        # Rule 5: spend_date format and future check
        spend_date_str = str(row.get("spend_date", ""))
        try:
            spend_date = datetime.strptime(spend_date_str, "%Y-%m-%d").date()
            if spend_date > ref_date:
                row_errors.append(
                    {
                        "field": "spend_date",
                        "error": f"Future date '{spend_date_str}' not allowed.",
                    }
                )
        except ValueError:
            row_errors.append(
                {
                    "field": "spend_date",
                    "error": f"Invalid date format '{spend_date_str}'. Must be YYYY-MM-DD.",
                }
            )

        # Rule 6: vendor non-empty
        vendor = str(row.get("vendor", "")).strip()
        if not vendor:
            row_errors.append(
                {
                    "field": "vendor",
                    "error": "Vendor must not be empty.",
                }
            )

        # Rule 7: fx_rate for non-USD
        if currency != "USD" and currency in VALID_CURRENCIES:
            fx_rate = row.get("fx_rate")
            if fx_rate is None or (isinstance(fx_rate, float) and fx_rate != fx_rate):
                row_errors.append(
                    {
                        "field": "fx_rate",
                        "error": f"fx_rate is required for non-USD currency '{currency}'.",
                    }
                )
            else:
                try:
                    fx_val = float(fx_rate)
                    if fx_val < 0.1 or fx_val > 500:
                        row_errors.append(
                            {
                                "field": "fx_rate",
                                "error": f"fx_rate {fx_val} out of range [0.1, 500].",
                            }
                        )
                except (TypeError, ValueError):
                    row_errors.append(
                        {
                            "field": "fx_rate",
                            "error": f"Invalid fx_rate value: '{fx_rate}'.",
                        }
                    )

        if row_errors:
            errors.append(
                {
                    "row_index": idx,
                    "row_data": row,
                    "errors": row_errors,
                }
            )

    state["validation_errors"] = errors
    state["validation_complete"] = True
    state["status"] = "VALIDATING"

    error_count = len(errors)
    total = len(records)
    logger.info("Validation complete: %d errors in %d rows", error_count, total)

    return {
        "status": "success",
        "total_rows": total,
        "valid_count": total - error_count,
        "error_count": error_count,
    }


def request_user_fix(
    tool_context: Any,
    row_index: int,
    field: str,
    current_value: str,
    error_message: str,
) -> dict:
    """Queue a fix request for the user."""
    state = tool_context.state
    fix_request = {
        "row_index": row_index,
        "field": field,
        "current_value": current_value,
        "error_message": error_message,
    }
    state["pending_fixes"].append(fix_request)
    state["status"] = "WAITING_FOR_USER"

    logger.info("Fix requested: row %d, field '%s'", row_index, field)
    return {
        "status": "fix_requested",
        "row_index": row_index,
        "field": field,
        "error_message": error_message,
    }


def write_fix(
    tool_context: Any,
    row_index: int,
    field: str,
    new_value: Any,
) -> dict:
    """Apply a user's fix to a data record."""
    state = tool_context.state
    records = state.get("dataframe_records", [])

    if row_index < 0 or row_index >= len(records):
        return {"status": "error", "message": f"Row index {row_index} out of range."}

    old_value = records[row_index].get(field)
    records[row_index][field] = new_value

    # Remove matching pending fix
    state["pending_fixes"] = [
        f
        for f in state["pending_fixes"]
        if not (f["row_index"] == row_index and f["field"] == field)
    ]

    # Update status
    if not state["pending_fixes"]:
        state["status"] = "RUNNING"
    else:
        state["status"] = "FIXING"

    logger.info("Fixed row %d, field '%s': '%s' -> '%s'", row_index, field, old_value, new_value)
    return {
        "status": "fixed",
        "row_index": row_index,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "remaining_fixes": len(state["pending_fixes"]),
    }
