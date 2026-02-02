"""Tests for validation tools — Story 2.2."""

from unittest.mock import MagicMock

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
        field_errors = [e for e in errors for err in e["errors"] if err["field"] == "employee_id"]
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
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["dataframe_records"][0]["dept"] == "Engineering"

    def test_removes_from_pending_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert len(ctx.state["pending_fixes"]) == 0

    def test_sets_running_when_no_more_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["status"] == "RUNNING"

    def test_stays_fixing_with_remaining_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad dept",
            },
            {"row_index": 0, "field": "amount", "current_value": -1, "error_message": "Bad amount"},
        ]
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="Engineering")
        assert ctx.state["status"] == "FIXING"
