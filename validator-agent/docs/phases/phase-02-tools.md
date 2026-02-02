# Phase 2: Tools

Phase 2 implements all 8 FunctionTool implementations across three tool modules: ingestion (file upload and CSV/XLSX reading), validation (7 business rules plus fix lifecycle), and processing (transform and package Excel artifacts).

**Stories:** 2.1, 2.2, 2.3
**Depends on:** Phase 1 (PipelineState model)
**Quality check:** `cd validator-agent && pytest tests/tools/ -v`

---

## Story 2.1: Ingestion tools — request_file_upload, ingest_file, ingest_uploaded_file {#story-2.1}

### Summary

Implement the three ingestion tools that handle file upload signaling, CSV/XLSX file reading from disk, and reading uploaded files from the ADK ArtifactService. These tools populate session state with parsed dataframe records and column metadata.

### Test (write first)

**File: `tests/fixtures/test_data.csv`**

```csv
employee_id,dept,amount,currency,spend_date,vendor,fx_rate
EMP001,Engineering,1500.00,USD,2024-01-15,Acme Corp,1.0
EMP002,Marketing,2500.50,EUR,2024-02-20,Beta Inc,1.08
EMP003,Sales,750.00,GBP,2024-03-10,Gamma Ltd,1.27
```

**File: `tests/tools/__init__.py`** (empty)

**File: `tests/tools/test_ingestion.py`**

```python
"""Tests for ingestion tools — Story 2.1."""
import pathlib
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


class TestRequestFileUpload:
    """request_file_upload returns a dict signaling the UI to show upload dialog."""

    def test_returns_waiting_status(self):
        ctx = MagicMock()
        ctx.state = {}
        result = request_file_upload(ctx)
        assert result["status"] == "waiting_for_upload"

    def test_returns_accepted_formats(self):
        ctx = MagicMock()
        ctx.state = {}
        result = request_file_upload(ctx)
        assert "accepted_formats" in result
        assert ".csv" in result["accepted_formats"]
        assert ".xlsx" in result["accepted_formats"]


class TestIngestFile:
    """ingest_file reads CSV/XLSX from disk and populates state."""

    def test_reads_csv(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        result = ingest_file(ctx, file_path=csv_path)
        assert result["status"] == "success"
        assert result["row_count"] == 3
        assert "employee_id" in result["columns"]

    def test_populates_state_records(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert len(ctx.state["dataframe_records"]) == 3

    def test_populates_state_columns(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert "employee_id" in ctx.state["dataframe_columns"]
        assert "dept" in ctx.state["dataframe_columns"]

    def test_sets_status_running(self):
        ctx = MagicMock()
        ctx.state = {}
        csv_path = str(FIXTURES / "test_data.csv")
        ingest_file(ctx, file_path=csv_path)
        assert ctx.state["status"] == "RUNNING"

    def test_unsupported_extension_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path="/tmp/data.json")
        assert result["status"] == "error"

    def test_missing_file_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        result = ingest_file(ctx, file_path="/tmp/nonexistent_file.csv")
        assert result["status"] == "error"


class TestIngestUploadedFile:
    """ingest_uploaded_file reads from ADK ArtifactService."""

    @pytest.mark.asyncio
    async def test_loads_artifact_and_parses(self):
        # Create a CSV in memory
        df = pd.DataFrame(
            {
                "employee_id": ["EMP001"],
                "dept": ["Engineering"],
                "amount": [1000.0],
                "currency": ["USD"],
                "spend_date": ["2024-01-15"],
                "vendor": ["Test Corp"],
                "fx_rate": [1.0],
            }
        )
        csv_bytes = df.to_csv(index=False).encode()

        ctx = MagicMock()
        ctx.state = {"uploaded_file": "upload_test.csv"}
        artifact_mock = MagicMock()
        artifact_mock.inline_data.data = csv_bytes
        artifact_mock.inline_data.mime_type = "text/csv"
        ctx.load_artifact = AsyncMock(return_value=artifact_mock)

        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "success"
        assert result["row_count"] == 1
        assert ctx.state["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_no_uploaded_file_returns_error(self):
        ctx = MagicMock()
        ctx.state = {}
        ctx.load_artifact = AsyncMock(return_value=None)
        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_artifact_not_found_returns_error(self):
        ctx = MagicMock()
        ctx.state = {"uploaded_file": "missing.csv"}
        ctx.load_artifact = AsyncMock(return_value=None)
        result = await ingest_uploaded_file(ctx)
        assert result["status"] == "error"
```

### Implementation

**File: `app/tools/ingestion.py`**

```python
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
```

**Update `app/tools/__init__.py`:**

```python
"""Tool implementations."""
from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload

__all__ = ["request_file_upload", "ingest_file", "ingest_uploaded_file"]
```

### Success criteria

- [ ] `request_file_upload` returns `status='waiting_for_upload'` with `accepted_formats`
- [ ] `ingest_file` reads CSV and populates state with records and columns
- [ ] `ingest_file` sets `state['status'] = 'RUNNING'`
- [ ] `ingest_file` returns error for unsupported file types
- [ ] `ingest_file` returns error for missing files
- [ ] `ingest_uploaded_file` loads artifact from `tool_context.load_artifact()`
- [ ] `ingest_uploaded_file` returns error if state has no `uploaded_file`
- [ ] `ingest_uploaded_file` returns error if artifact not found
- [ ] `ingest_uploaded_file` sets `state['status'] = 'RUNNING'`
- [ ] All tests in `tests/tools/test_ingestion.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/tools/test_ingestion.py -v
```

### Commit message

```
feat(tools): add ingestion tools for file upload and parsing

- request_file_upload signals UI for file upload dialog
- ingest_file reads CSV/XLSX from disk path
- ingest_uploaded_file reads from ADK ArtifactService
- All tools populate shared session state
```

---

## Story 2.2: Validation tools — validate_data, request_user_fix, write_fix {#story-2.2}

### Summary

Implement the three validation tools that enforce 7 business rules against spreadsheet data and manage the error-fix lifecycle with users. The 7 rules cover employee_id format and uniqueness, department enum, amount range, currency enum, spend_date format and future-date check, vendor non-empty, and fx_rate requirements for non-USD currencies.

### Test (write first)

**File: `tests/tools/test_validation.py`**

```python
"""Tests for validation tools — Story 2.2."""
from unittest.mock import MagicMock

import pytest

from app.tools.validation import request_user_fix, validate_data, write_fix


def _make_context(records: list[dict], **extra_state) -> MagicMock:
    """Helper to create a mock tool context with state."""
    ctx = MagicMock()
    columns = list(records[0].keys()) if records else []
    ctx.state = {
        "dataframe_records": records,
        "dataframe_columns": columns,
        "validation_errors": [],
        "validation_complete": False,
        "pending_fixes": [],
        "status": "RUNNING",
        **extra_state,
    }
    return ctx


VALID_ROW = {
    "employee_id": "EMP001",
    "dept": "Engineering",
    "amount": 1500.00,
    "currency": "USD",
    "spend_date": "2024-01-15",
    "vendor": "Acme Corp",
    "fx_rate": 1.0,
}


class TestValidateDataClean:
    """validate_data with all-valid data should return success."""

    def test_clean_data_returns_success(self):
        ctx = _make_context([VALID_ROW.copy()])
        result = validate_data(ctx)
        assert result["status"] == "success"
        assert result["error_count"] == 0

    def test_sets_validation_complete(self):
        ctx = _make_context([VALID_ROW.copy()])
        validate_data(ctx)
        assert ctx.state["validation_complete"] is True

    def test_sets_status_validating(self):
        ctx = _make_context([VALID_ROW.copy()])
        validate_data(ctx)
        assert ctx.state["status"] == "VALIDATING"


class TestValidateDataEmployeeId:
    """Rule 1: employee_id must match EMP\\d{3,} and be unique."""

    def test_invalid_employee_id_pattern(self):
        row = {**VALID_ROW, "employee_id": "INVALID"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0
        errors = ctx.state["validation_errors"]
        field_errors = [
            e for e in errors for err in e["errors"] if err["field"] == "employee_id"
        ]
        assert len(field_errors) > 0

    def test_duplicate_employee_id(self):
        rows = [VALID_ROW.copy(), {**VALID_ROW, "employee_id": "EMP001"}]
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataDept:
    """Rule 2: dept must be one of the allowed departments."""

    def test_invalid_dept(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataAmount:
    """Rule 3: amount must be > 0 and <= 100000."""

    def test_zero_amount(self):
        row = {**VALID_ROW, "amount": 0}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_negative_amount(self):
        row = {**VALID_ROW, "amount": -100}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_amount_too_large(self):
        row = {**VALID_ROW, "amount": 100001}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataCurrency:
    """Rule 4: currency must be a valid ISO 4217 code."""

    def test_invalid_currency(self):
        row = {**VALID_ROW, "currency": "XYZ"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataSpendDate:
    """Rule 5: spend_date must be YYYY-MM-DD and not in the future."""

    def test_invalid_date_format(self):
        row = {**VALID_ROW, "spend_date": "01/15/2024"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_future_date(self):
        row = {**VALID_ROW, "spend_date": "2099-12-31"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataVendor:
    """Rule 6: vendor must not be empty."""

    def test_empty_vendor(self):
        row = {**VALID_ROW, "vendor": ""}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_whitespace_vendor(self):
        row = {**VALID_ROW, "vendor": "   "}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataFxRate:
    """Rule 7: fx_rate required for non-USD currencies and in [0.1, 500]."""

    def test_missing_fx_rate_non_usd(self):
        row = {**VALID_ROW, "currency": "EUR", "fx_rate": None}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_fx_rate_too_low(self):
        row = {**VALID_ROW, "currency": "EUR", "fx_rate": 0.01}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_fx_rate_too_high(self):
        row = {**VALID_ROW, "currency": "EUR", "fx_rate": 600}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestRequestUserFix:
    """request_user_fix appends to pending_fixes and sets status."""

    def test_appends_fix_request(self):
        ctx = _make_context([VALID_ROW.copy()])
        request_user_fix(
            ctx,
            row_index=0,
            field="dept",
            current_value="InvalidDept",
            error_message="Invalid department",
        )
        assert len(ctx.state["pending_fixes"]) == 1
        fix = ctx.state["pending_fixes"][0]
        assert fix["row_index"] == 0
        assert fix["field"] == "dept"

    def test_sets_waiting_for_user_status(self):
        ctx = _make_context([VALID_ROW.copy()])
        request_user_fix(ctx, row_index=0, field="dept", current_value="X", error_message="Bad")
        assert ctx.state["status"] == "WAITING_FOR_USER"


class TestWriteFix:
    """write_fix updates the record and removes from pending_fixes."""

    def test_updates_record_value(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "InvalidDept", "error_message": "Bad"}
        ]
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["dataframe_records"][0]["dept"] == "Engineering"

    def test_removes_from_pending_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "InvalidDept", "error_message": "Bad"}
        ]
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert len(ctx.state["pending_fixes"]) == 0

    def test_sets_running_when_no_more_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "InvalidDept", "error_message": "Bad"}
        ]
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["status"] == "RUNNING"

    def test_stays_fixing_with_remaining_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "InvalidDept", "error_message": "Bad dept"},
            {"row_index": 0, "field": "amount", "current_value": -1, "error_message": "Bad amount"},
        ]
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["status"] == "FIXING"
```

### Implementation

**File: `app/tools/validation.py`**

```python
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
    "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "MXN",
    "BRL", "KRW", "SEK", "NOK", "DKK", "NZD", "SGD", "HKD", "TRY", "ZAR",
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
            row_errors.append({
                "field": "employee_id",
                "error": f"Invalid employee_id format: '{emp_id}'. Must match EMP followed by 3+ digits.",
            })

        # Rule 1b: employee_id uniqueness
        if emp_id in seen_ids:
            row_errors.append({
                "field": "employee_id",
                "error": f"Duplicate employee_id '{emp_id}' — also at row {seen_ids[emp_id]}.",
            })
        seen_ids[emp_id] = idx

        # Rule 2: department enum
        dept = str(row.get("dept", ""))
        if dept not in VALID_DEPARTMENTS:
            row_errors.append({
                "field": "dept",
                "error": f"Invalid department '{dept}'. Must be one of: {sorted(VALID_DEPARTMENTS)}.",
            })

        # Rule 3: amount range
        try:
            amount = float(row.get("amount", 0))
            if amount <= 0 or amount > 100000:
                row_errors.append({
                    "field": "amount",
                    "error": f"Amount {amount} out of range. Must be > 0 and <= 100,000.",
                })
        except (TypeError, ValueError):
            row_errors.append({
                "field": "amount",
                "error": f"Invalid amount value: '{row.get('amount')}'.",
            })

        # Rule 4: currency enum
        currency = str(row.get("currency", ""))
        if currency not in VALID_CURRENCIES:
            row_errors.append({
                "field": "currency",
                "error": f"Invalid currency '{currency}'. Must be a valid ISO 4217 code.",
            })

        # Rule 5: spend_date format and future check
        spend_date_str = str(row.get("spend_date", ""))
        try:
            spend_date = datetime.strptime(spend_date_str, "%Y-%m-%d").date()
            if spend_date > ref_date:
                row_errors.append({
                    "field": "spend_date",
                    "error": f"Future date '{spend_date_str}' not allowed.",
                })
        except ValueError:
            row_errors.append({
                "field": "spend_date",
                "error": f"Invalid date format '{spend_date_str}'. Must be YYYY-MM-DD.",
            })

        # Rule 6: vendor non-empty
        vendor = str(row.get("vendor", "")).strip()
        if not vendor:
            row_errors.append({
                "field": "vendor",
                "error": "Vendor must not be empty.",
            })

        # Rule 7: fx_rate for non-USD
        if currency != "USD" and currency in VALID_CURRENCIES:
            fx_rate = row.get("fx_rate")
            if fx_rate is None or (isinstance(fx_rate, float) and fx_rate != fx_rate):
                row_errors.append({
                    "field": "fx_rate",
                    "error": f"fx_rate is required for non-USD currency '{currency}'.",
                })
            else:
                try:
                    fx_val = float(fx_rate)
                    if fx_val < 0.1 or fx_val > 500:
                        row_errors.append({
                            "field": "fx_rate",
                            "error": f"fx_rate {fx_val} out of range [0.1, 500].",
                        })
                except (TypeError, ValueError):
                    row_errors.append({
                        "field": "fx_rate",
                        "error": f"Invalid fx_rate value: '{fx_rate}'.",
                    })

        if row_errors:
            errors.append({
                "row_index": idx,
                "row_data": row,
                "errors": row_errors,
            })

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
```

**Update `app/tools/__init__.py`:**

```python
"""Tool implementations."""
from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload
from app.tools.validation import request_user_fix, validate_data, write_fix

__all__ = [
    "request_file_upload",
    "ingest_file",
    "ingest_uploaded_file",
    "validate_data",
    "request_user_fix",
    "write_fix",
]
```

### Success criteria

- [ ] `validate_data` catches invalid `employee_id` patterns
- [ ] `validate_data` catches duplicate `employee_id` values
- [ ] `validate_data` catches invalid `dept` values
- [ ] `validate_data` catches amount out of range (<= 0 or > 100000)
- [ ] `validate_data` catches invalid `currency` values
- [ ] `validate_data` catches invalid `spend_date` format and future dates
- [ ] `validate_data` catches empty `vendor`
- [ ] `validate_data` catches missing `fx_rate` for non-USD currencies
- [ ] `validate_data` catches `fx_rate` out of range [0.1, 500]
- [ ] `validate_data` sets `validation_complete=True`
- [ ] `request_user_fix` appends to `pending_fixes` and sets `WAITING_FOR_USER`
- [ ] `write_fix` updates the record value and removes from `pending_fixes`
- [ ] `write_fix` sets `status='RUNNING'` when `pending_fixes` is empty
- [ ] All tests in `tests/tools/test_validation.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/tools/test_validation.py -v
```

### Commit message

```
feat(tools): add validation tools with 7 business rules

- validate_data checks employee_id, dept, amount, currency, spend_date, vendor, fx_rate
- request_user_fix queues fix requests with WAITING_FOR_USER status
- write_fix applies corrections and transitions back to RUNNING
```

---

## Story 2.3: Processing tools — transform_data, package_results {#story-2.3}

### Summary

Implement the transformation and Excel artifact packaging tools. `transform_data` adds computed columns to data records. `package_results` separates valid and invalid rows into success.xlsx and errors.xlsx artifacts saved via the ADK ArtifactService.

### Test (write first)

**File: `tests/tools/test_processing.py`**

```python
"""Tests for processing tools — Story 2.3."""
import io
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.tools.processing import package_results, transform_data


def _make_context(records: list[dict], **extra_state) -> MagicMock:
    """Helper to create a mock tool context with state."""
    ctx = MagicMock()
    columns = list(records[0].keys()) if records else []
    ctx.state = {
        "dataframe_records": records,
        "dataframe_columns": columns,
        "validation_errors": [],
        "artifacts": {},
        "status": "RUNNING",
        **extra_state,
    }
    return ctx


SAMPLE_ROW = {
    "employee_id": "EMP001",
    "dept": "Engineering",
    "amount": 1500.00,
    "currency": "USD",
    "spend_date": "2024-01-15",
    "vendor": "Acme Corp",
    "fx_rate": 1.0,
}


class TestTransformDataDefaultValue:
    """transform_data with default_value adds a static column."""

    def test_adds_static_column(self):
        ctx = _make_context([SAMPLE_ROW.copy(), SAMPLE_ROW.copy()])
        result = transform_data(ctx, new_column_name="region", default_value="US")
        assert result["status"] == "success"
        for record in ctx.state["dataframe_records"]:
            assert record["region"] == "US"

    def test_updates_columns_list(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        transform_data(ctx, new_column_name="region", default_value="US")
        assert "region" in ctx.state["dataframe_columns"]

    def test_no_data_returns_error(self):
        ctx = _make_context([])
        ctx.state["dataframe_records"] = []
        result = transform_data(ctx, new_column_name="region", default_value="US")
        assert result["status"] == "error"


class TestTransformDataExpression:
    """transform_data with expression computes values per row."""

    def test_expression_column(self):
        row1 = {**SAMPLE_ROW, "amount": 100.0, "fx_rate": 1.1}
        row2 = {**SAMPLE_ROW, "employee_id": "EMP002", "amount": 200.0, "fx_rate": 0.9}
        ctx = _make_context([row1, row2])
        result = transform_data(
            ctx,
            new_column_name="amount_usd",
            expression="round(row['amount'] * row['fx_rate'], 2)",
        )
        assert result["status"] == "success"
        assert ctx.state["dataframe_records"][0]["amount_usd"] == 110.0
        assert ctx.state["dataframe_records"][1]["amount_usd"] == 180.0

    def test_sets_status_transforming(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        transform_data(ctx, new_column_name="x", default_value="y")
        assert ctx.state["status"] == "TRANSFORMING"


class TestPackageResults:
    """package_results creates success.xlsx and errors.xlsx artifacts."""

    @pytest.mark.asyncio
    async def test_separates_valid_and_invalid(self):
        row_valid = SAMPLE_ROW.copy()
        row_invalid = {**SAMPLE_ROW, "employee_id": "EMP002"}
        ctx = _make_context([row_valid, row_invalid])
        ctx.state["validation_errors"] = [
            {"row_index": 1, "row_data": row_invalid, "errors": [{"field": "dept", "error": "bad"}]}
        ]
        saved_artifacts = {}

        async def mock_save(filename, artifact):
            saved_artifacts[filename] = artifact

        ctx.save_artifact = mock_save

        result = await package_results(ctx)
        assert result["status"] == "success"
        assert "success.xlsx" in saved_artifacts
        assert "errors.xlsx" in saved_artifacts

    @pytest.mark.asyncio
    async def test_sets_completed_status(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        ctx.save_artifact = AsyncMock()
        result = await package_results(ctx)
        assert ctx.state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_artifacts_in_state(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        ctx.save_artifact = AsyncMock()
        await package_results(ctx)
        assert "success.xlsx" in ctx.state["artifacts"]
        assert "errors.xlsx" in ctx.state["artifacts"]

    @pytest.mark.asyncio
    async def test_success_artifact_is_valid_excel(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        saved = {}

        async def mock_save(filename, artifact):
            saved[filename] = artifact

        ctx.save_artifact = mock_save
        await package_results(ctx)

        # The artifact should contain valid Excel bytes
        artifact = saved["success.xlsx"]
        excel_bytes = artifact.inline_data.data
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert len(df) == 1
        assert "employee_id" in df.columns

    @pytest.mark.asyncio
    async def test_errors_artifact_has_errors_column(self):
        row_invalid = {**SAMPLE_ROW, "employee_id": "BAD"}
        ctx = _make_context([row_invalid])
        ctx.state["validation_errors"] = [
            {
                "row_index": 0,
                "row_data": row_invalid,
                "errors": [{"field": "employee_id", "error": "Bad ID"}],
            }
        ]
        saved = {}

        async def mock_save(filename, artifact):
            saved[filename] = artifact

        ctx.save_artifact = mock_save
        await package_results(ctx)

        artifact = saved["errors.xlsx"]
        excel_bytes = artifact.inline_data.data
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert "_errors" in df.columns
```

### Implementation

**File: `app/tools/processing.py`**

```python
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
                row[new_column_name] = eval(expression, {"__builtins__": {}}, {"row": row, "round": round})
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

    success_artifact = Part.from_data(
        data=success_bytes,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    await tool_context.save_artifact(filename="success.xlsx", artifact=success_artifact)

    # errors.xlsx
    errors_buf = io.BytesIO()
    df_errors = pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame()
    df_errors.to_excel(errors_buf, index=False)
    errors_bytes = errors_buf.getvalue()

    errors_artifact = Part.from_data(
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
```

**Update `app/tools/__init__.py`:**

```python
"""Tool implementations."""
from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload
from app.tools.processing import package_results, transform_data
from app.tools.validation import request_user_fix, validate_data, write_fix

__all__ = [
    "request_file_upload",
    "ingest_file",
    "ingest_uploaded_file",
    "validate_data",
    "request_user_fix",
    "write_fix",
    "transform_data",
    "package_results",
]
```

### Success criteria

- [ ] `transform_data` adds a static column to all records
- [ ] `transform_data` adds a computed column using expression
- [ ] `transform_data` updates `dataframe_columns` list
- [ ] `transform_data` returns error if no data loaded
- [ ] `transform_data` sets `status='TRANSFORMING'`
- [ ] `package_results` creates `success.xlsx` with valid rows only
- [ ] `package_results` creates `errors.xlsx` with invalid rows and `_errors` column
- [ ] `package_results` saves artifacts via `tool_context.save_artifact()`
- [ ] `package_results` sets `state['artifacts']` with artifact names
- [ ] `package_results` sets `state['status'] = 'COMPLETED'`
- [ ] Artifact bytes are valid Excel files parseable by pandas
- [ ] All tests in `tests/tools/test_processing.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/tools/test_processing.py -v
```

### Commit message

```
feat(tools): add transform and packaging tools

- transform_data adds static or computed columns to records
- package_results separates valid/invalid rows into Excel artifacts
- Artifacts saved via ADK ArtifactService with proper MIME types
```
