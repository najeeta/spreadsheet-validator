"""Validation tools — 7 business rules and fix lifecycle management."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional

from app.fix_utils import FIX_BATCH_SIZE

logger = logging.getLogger(__name__)

VALID_DEPARTMENTS = {"FIN", "HR", "ENG", "OPS"}

VALID_CURRENCIES = {"USD", "EUR", "GBP", "INR"}

EMPLOYEE_ID_PATTERN = re.compile(r"^[A-Z0-9]{4,12}$")


def validate_data(tool_context: Any, as_of_date: Optional[str] = None) -> dict:
    """Validate all records against business rules.

    Rules:
    1. employee_id: 4-12 alphanumeric characters (A-Z0-9)
    2. dept: Must be one of FIN, HR, ENG, OPS
    3. amount: > 0 and <= 100,000
    4. currency: Must be USD, EUR, GBP, or INR
    5. spend_date: YYYY-MM-DD format, not in the future
    6. vendor: Non-empty
    7. fx_rate: Required for non-USD, range [0.1, 500]
    8. Duplicate check: (employee_id, spend_date) pair must be unique

    Note: CFO approval (FIN dept + amount > 50k) is handled as a computed
    column (approval_required) in package_results, not as a validation error.

    Supports incremental validation: rows with unchanged fingerprints that
    were previously valid are skipped (except for duplicate pair checks).
    """
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

    # Get fingerprints for incremental validation
    fingerprints = state.get("row_fingerprints", [])
    prev_valid = state.get("validated_row_fingerprints", {})

    # If fingerprints are missing or length mismatch, recompute
    if len(fingerprints) != len(records):
        from app.utils import compute_all_fingerprints

        fingerprints = compute_all_fingerprints(records)
        state["row_fingerprints"] = fingerprints

    pending: list[dict] = []
    seen_pairs: dict[tuple[str, str], int] = {}
    new_valid_fingerprints: dict[str, bool] = {}
    skipped_count = 0
    error_row_count = 0

    # Exclude rows already skipped by the user (they're done, flagged as errors)
    skipped_indices = set(state.get("skipped_rows", []))

    for idx, row in enumerate(records):
        fp = fingerprints[idx] if idx < len(fingerprints) else ""

        # Extract keys for duplicate pair check (must always happen)
        emp_id = str(row.get("employee_id", ""))
        spend_date_str = str(row.get("spend_date", ""))
        pair = (emp_id, spend_date_str)

        # Check for duplicate (employee_id, spend_date) pair
        is_duplicate = pair in seen_pairs
        first_occurrence_idx = seen_pairs.get(pair)
        seen_pairs[pair] = idx

        # Skip rows already marked as skipped by the user
        # Mark them as invalid in fingerprint cache so state reflects true data quality
        if idx in skipped_indices:
            skipped_count += 1
            if fp:
                new_valid_fingerprints[fp] = False
            continue

        # Check if we can skip this row (unchanged and previously valid)
        # Note: we still need to check duplicates even for skipped rows
        if fp and fp in prev_valid and prev_valid[fp] is True and not is_duplicate:
            # Row is unchanged and was valid last time, skip full validation
            new_valid_fingerprints[fp] = True
            skipped_count += 1
            continue

        row_errors: list[dict] = []

        # Rule 1: employee_id format (4-12 alphanumeric)
        if not EMPLOYEE_ID_PATTERN.match(emp_id):
            row_errors.append(
                {
                    "field": "employee_id",
                    "error": f"Invalid employee_id format: '{emp_id}'. Must be 4-12 alphanumeric characters (A-Z, 0-9).",
                }
            )

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
        amount = 0.0
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
                    "error": f"Invalid currency '{currency}'. Must be one of: {sorted(VALID_CURRENCIES)}.",
                }
            )

        # Rule 5: spend_date format and future check
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

        # Rule 8: duplicate (employee_id, spend_date) pair
        if is_duplicate:
            row_errors.append(
                {
                    "field": "employee_id",
                    "error": f"Duplicate (employee_id, spend_date) pair '{emp_id}', '{spend_date_str}' — also at row {first_occurrence_idx}.",
                }
            )

        # Track validation result for this fingerprint
        if fp:
            new_valid_fingerprints[fp] = len(row_errors) == 0

        if row_errors:
            error_row_count += 1
            # Add each error to all_errors
            for field_err in row_errors:
                pending.append(
                    {
                        "row_index": idx,
                        "field": field_err["field"],
                        "current_value": str(row.get(field_err["field"], "")),
                        "error_message": field_err["error"],
                    }
                )

    # Store validated fingerprints for next run
    state["validated_row_fingerprints"] = new_valid_fingerprints

    total = len(records)

    if pending:
        # Store all errors as flat list (single source of truth)
        state["all_errors"] = pending

        # Batch first FIX_BATCH_SIZE rows into pending_review
        errors_by_row: dict[int, list[dict]] = defaultdict(list)
        for err in pending:
            errors_by_row[err["row_index"]].append(err)

        batch_row_indices = sorted(errors_by_row.keys())[:FIX_BATCH_SIZE]
        batch: list[dict] = []
        for row_idx in batch_row_indices:
            batch.extend(errors_by_row[row_idx])

        state["pending_review"] = batch
        state["status"] = "WAITING_FOR_USER"
        state["waiting_since"] = time.time()

        batch_size = len(batch_row_indices)

        logger.info(
            "Validation found %d errors in %d rows (skipped %d unchanged valid rows) - WAITING_FOR_USER, batch=%d rows",
            error_row_count,
            total,
            skipped_count,
            batch_size,
        )

        # Return explicit STOP instruction when errors exist
        return {
            "status": "waiting_for_fixes",
            "action": "STOP - Do NOT call process_results. Wait for user to provide fixes.",
            "total_rows": total,
            "valid_count": total - error_row_count,
            "error_count": error_row_count,
            "pending_review_count": len(batch),
            "batch_size": batch_size,
            "skipped_unchanged": skipped_count,
            "message": f"Found {error_row_count} rows with errors. Showing batch of {batch_size} rows. The user must fix these before processing can continue.",
        }

    # No errors - validation complete
    state["all_errors"] = []
    state["pending_review"] = []
    state["status"] = "VALIDATING"
    state["waiting_since"] = None

    logger.info(
        "Validation complete: %d errors in %d rows (skipped %d unchanged valid rows)",
        error_row_count,
        total,
        skipped_count,
    )

    return {
        "status": "success",
        "action": "Proceed to process_results - all data is valid.",
        "total_rows": total,
        "valid_count": total - error_row_count,
        "error_count": error_row_count,
        "skipped_unchanged": skipped_count,
    }


def write_fix(
    tool_context: Any,
    row_index: int,
    field: str,
    new_value: Any,
) -> dict:
    """Apply a user's fix to a data record."""
    from app.fix_utils import apply_single_fix

    return apply_single_fix(tool_context.state, row_index, field, new_value)


def batch_write_fixes(tool_context: Any, row_index: int, fixes: dict[str, Any]) -> dict:
    """Apply multiple fixes to one row at once.

    Args:
        row_index: The row index to fix.
        fixes: A dict mapping field names to new values, e.g. {"dept": "ENG", "amount": "1500"}.
    """
    from app.fix_utils import apply_batch_fixes

    return apply_batch_fixes(tool_context.state, row_index, fixes)


def skip_row(tool_context: Any, row_index: int) -> dict:
    """Skip a single row — user chose not to fix it."""
    from app.fix_utils import apply_skip_row

    return apply_skip_row(tool_context.state, row_index)


def skip_fixes(tool_context: Any) -> dict:
    """Skip ALL remaining pending fixes (timeout or user chose skip-all)."""
    from app.fix_utils import apply_skip_all

    return apply_skip_all(tool_context.state)
