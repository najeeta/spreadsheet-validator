"""Tests for validation tools — updated for new business rules."""

from unittest.mock import MagicMock

from app.tools.validation import (
    FIX_BATCH_SIZE,
    batch_write_fixes,
    request_user_fix,
    skip_fixes,
    skip_row,
    validate_data,
    write_fix,
)
from app.utils import compute_all_fingerprints, compute_row_fingerprint


def _make_context(records: list[dict], **extra_state) -> MagicMock:
    """Helper to create a mock tool context with state."""
    ctx = MagicMock()
    columns = list(records[0].keys()) if records else []
    ctx.state = {
        "dataframe_records": records,
        "dataframe_columns": columns,
        "pending_fixes": [],
        "status": "RUNNING",
        **extra_state,
    }
    return ctx


# Valid row per new spec: employee_id=4-12 alphanumeric, dept in {FIN,HR,ENG,OPS}, currency in {USD,EUR,GBP,INR}
VALID_ROW = {
    "employee_id": "EMP001",  # 6 chars, all alphanumeric
    "dept": "ENG",
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

    def test_sets_status_validating(self):
        ctx = _make_context([VALID_ROW.copy()])
        validate_data(ctx)
        assert ctx.state["status"] == "VALIDATING"

    def test_clears_pending_fixes(self):
        ctx = _make_context([VALID_ROW.copy()])
        validate_data(ctx)
        assert ctx.state["pending_fixes"] == []


class TestValidateDataAutoPopulatesFixes:
    """validate_data auto-populates pending_fixes when errors found."""

    def test_sets_waiting_for_user_on_errors(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        validate_data(ctx)
        assert ctx.state["status"] == "WAITING_FOR_USER"

    def test_returns_waiting_for_fixes_status_on_errors(self):
        """Return value must clearly indicate STOP when errors exist.

        The return status should be 'waiting_for_fixes' (not 'success') and
        include an explicit action message telling the agent to stop and wait.
        """
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["status"] == "waiting_for_fixes"
        assert "STOP" in result["action"]
        assert "process_results" in result["action"]
        assert result["pending_fixes_count"] >= 1

    def test_returns_success_with_proceed_action_when_valid(self):
        """Return value must indicate proceed when no errors exist."""
        ctx = _make_context([VALID_ROW.copy()])
        result = validate_data(ctx)
        assert result["status"] == "success"
        assert "Proceed" in result["action"]
        assert result["error_count"] == 0

    def test_populates_pending_fixes_from_errors(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        validate_data(ctx)
        assert len(ctx.state["pending_fixes"]) == 1
        fix = ctx.state["pending_fixes"][0]
        assert fix["row_index"] == 0
        assert fix["field"] == "dept"
        assert fix["current_value"] == "InvalidDept"
        assert "Invalid department" in fix["error_message"]

    def test_multiple_errors_per_row(self):
        row = {**VALID_ROW, "dept": "Bad", "amount": -50}
        ctx = _make_context([row])
        validate_data(ctx)
        fixes = ctx.state["pending_fixes"]
        fields = {f["field"] for f in fixes}
        assert "dept" in fields
        assert "amount" in fields

    def test_errors_across_multiple_rows(self):
        rows = [
            {**VALID_ROW, "dept": "Bad"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        validate_data(ctx)
        fixes = ctx.state["pending_fixes"]
        row_indices = {f["row_index"] for f in fixes}
        assert 0 in row_indices
        assert 1 in row_indices


class TestValidateDataEmployeeId:
    """Rule 1: employee_id must be 4-12 alphanumeric characters (A-Z, 0-9)."""

    def test_valid_employee_id_patterns(self):
        # Test various valid patterns
        valid_ids = ["ABCD", "A1B2C3D4", "EMP001", "EMPLOYEE123", "123456789012"]
        for emp_id in valid_ids:
            row = {**VALID_ROW, "employee_id": emp_id}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] == 0, f"Expected {emp_id} to be valid"

    def test_employee_id_too_short(self):
        row = {**VALID_ROW, "employee_id": "ABC"}  # Only 3 chars
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0
        fixes = ctx.state["pending_fixes"]
        emp_errors = [f for f in fixes if f["field"] == "employee_id"]
        assert len(emp_errors) > 0

    def test_employee_id_too_long(self):
        row = {**VALID_ROW, "employee_id": "A" * 13}  # 13 chars
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_employee_id_invalid_chars(self):
        row = {**VALID_ROW, "employee_id": "EMP_001"}  # Underscore not allowed
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_employee_id_lowercase_invalid(self):
        row = {**VALID_ROW, "employee_id": "emp001"}  # Lowercase not allowed
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0


class TestValidateDataDuplicatePair:
    """Rule 8: (employee_id, spend_date) pair must be unique."""

    def test_same_employee_different_dates_valid(self):
        """Same employee_id with different spend_dates should be valid."""
        rows = [
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"},
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["error_count"] == 0

    def test_same_date_different_employees_valid(self):
        """Different employee_ids with same spend_date should be valid."""
        rows = [
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"},
            {**VALID_ROW, "employee_id": "EMP002", "spend_date": "2024-01-15"},
        ]
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["error_count"] == 0

    def test_duplicate_pair_detected(self):
        """Same (employee_id, spend_date) pair should be flagged as duplicate."""
        rows = [
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"},
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"},
        ]
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["error_count"] == 1  # Only second row has error
        fixes = ctx.state["pending_fixes"]
        dup_errors = [f for f in fixes if "Duplicate" in f["error_message"]]
        assert len(dup_errors) == 1
        assert dup_errors[0]["row_index"] == 1


class TestValidateDataDept:
    """Rule 2: dept must be one of FIN, HR, ENG, OPS."""

    def test_valid_departments(self):
        for dept in ["FIN", "HR", "ENG", "OPS"]:
            row = {**VALID_ROW, "dept": dept}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] == 0, f"Expected {dept} to be valid"

    def test_invalid_dept(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_old_dept_names_now_invalid(self):
        """Old department names like Engineering, Finance should now be invalid."""
        for dept in ["Engineering", "Finance", "Marketing", "Sales"]:
            row = {**VALID_ROW, "dept": dept}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] > 0, f"Expected {dept} to be invalid"


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
    """Rule 4: currency must be USD, EUR, GBP, or INR."""

    def test_valid_currencies(self):
        for currency in ["USD", "EUR", "GBP", "INR"]:
            row = {**VALID_ROW, "currency": currency, "fx_rate": 1.2}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] == 0, f"Expected {currency} to be valid"

    def test_invalid_currency(self):
        row = {**VALID_ROW, "currency": "XYZ"}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] > 0

    def test_old_currencies_now_invalid(self):
        """Currencies like JPY, CAD, CHF etc should now be invalid."""
        for currency in ["JPY", "CAD", "CHF", "CNY", "AUD"]:
            row = {**VALID_ROW, "currency": currency}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] > 0, f"Expected {currency} to be invalid"


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


class TestValidateDataCFOApproval:
    """CFO approval is now a computed column in package_results, not a validation error."""

    def test_fin_under_threshold_valid(self):
        row = {**VALID_ROW, "dept": "FIN", "amount": 50000}  # Exactly at threshold
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] == 0

    def test_fin_over_threshold_no_longer_an_error(self):
        """FIN + amount > 50k is valid data — CFO approval is handled as a computed column."""
        row = {**VALID_ROW, "dept": "FIN", "amount": 50001}
        ctx = _make_context([row])
        result = validate_data(ctx)
        assert result["error_count"] == 0

    def test_non_fin_over_threshold_valid(self):
        """Non-FIN departments don't need CFO approval even with high amounts."""
        for dept in ["HR", "ENG", "OPS"]:
            row = {**VALID_ROW, "dept": dept, "amount": 99999}
            ctx = _make_context([row])
            result = validate_data(ctx)
            assert result["error_count"] == 0, f"{dept} with high amount should be valid"


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
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert ctx.state["dataframe_records"][0]["dept"] == "ENG"

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
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
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
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
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
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert ctx.state["status"] == "FIXING"


class TestIncrementalValidation:
    """Tests for incremental validation using row fingerprints."""

    def test_skips_unchanged_valid_rows(self):
        """Second validation should skip rows that were valid and unchanged."""
        rows = [
            VALID_ROW.copy(),
            {**VALID_ROW, "employee_id": "EMP002", "spend_date": "2024-01-16"},
            {**VALID_ROW, "employee_id": "EMP003", "spend_date": "2024-01-17"},
        ]
        ctx = _make_context(rows)

        # First validation - all rows validated
        result1 = validate_data(ctx)
        assert result1["error_count"] == 0
        assert result1["skipped_unchanged"] == 0

        # Second validation - should skip all valid rows
        result2 = validate_data(ctx)
        assert result2["error_count"] == 0
        assert result2["skipped_unchanged"] == 3

    def test_revalidates_changed_rows(self):
        """After a fix, the changed row should be revalidated."""
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])

        # Setup fingerprints
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])

        # First validation - error found
        result1 = validate_data(ctx)
        assert result1["error_count"] == 1

        # Apply fix
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # Second validation - row should be revalidated (not skipped)
        result2 = validate_data(ctx)
        assert result2["error_count"] == 0
        assert result2["skipped_unchanged"] == 0  # Changed row was revalidated

    def test_invalid_rows_not_skipped(self):
        """Rows that had errors should always be revalidated."""
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])

        # First validation
        result1 = validate_data(ctx)
        assert result1["error_count"] == 1

        # Second validation - invalid row should NOT be skipped
        result2 = validate_data(ctx)
        assert result2["error_count"] == 1
        assert result2["skipped_unchanged"] == 0

    def test_duplicate_pair_check_includes_skipped_rows(self):
        """Skipped rows should still contribute to duplicate pair detection."""
        rows = [
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"},
            {**VALID_ROW, "employee_id": "EMP002", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)

        # First validation - both valid
        result1 = validate_data(ctx)
        assert result1["error_count"] == 0

        # Add a third row with duplicate pair of first row
        rows.append(
            {**VALID_ROW, "employee_id": "EMP001", "spend_date": "2024-01-15"}
        )  # Duplicate pair!
        ctx.state["dataframe_records"] = rows
        # Add fingerprint for new row
        ctx.state["row_fingerprints"].append(compute_row_fingerprint(rows[2]))

        # Second validation - should detect duplicate even though first row is skipped
        result2 = validate_data(ctx)
        assert result2["error_count"] == 1
        # First two rows should be skipped as unchanged valid
        assert result2["skipped_unchanged"] == 2

    def test_write_fix_updates_fingerprint(self):
        """write_fix should update the fingerprint of the modified row."""
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]

        old_fp = ctx.state["row_fingerprints"][0]

        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        new_fp = ctx.state["row_fingerprints"][0]
        assert old_fp != new_fp
        assert new_fp == compute_row_fingerprint(ctx.state["dataframe_records"][0])

    def test_write_fix_invalidates_old_fingerprint(self):
        """write_fix should remove old fingerprint from valid cache."""
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        fps = compute_all_fingerprints([row])
        ctx.state["row_fingerprints"] = fps
        ctx.state["validated_row_fingerprints"] = {fps[0]: False}  # Was invalid
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]

        old_fp = fps[0]
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # Old fingerprint should be removed from cache
        assert old_fp not in ctx.state["validated_row_fingerprints"]

    def test_mixed_valid_invalid_rows(self):
        """Only valid unchanged rows should be skipped on revalidation."""
        rows = [
            VALID_ROW.copy(),  # Valid
            {
                **VALID_ROW,
                "employee_id": "EMP002",
                "dept": "InvalidDept",
                "spend_date": "2024-01-16",
            },  # Invalid
            {**VALID_ROW, "employee_id": "EMP003", "spend_date": "2024-01-17"},  # Valid
        ]
        ctx = _make_context(rows)

        # First validation
        result1 = validate_data(ctx)
        assert result1["error_count"] == 1
        assert result1["valid_count"] == 2
        assert result1["skipped_unchanged"] == 0

        # Second validation - only valid rows should be skipped
        result2 = validate_data(ctx)
        assert result2["error_count"] == 1
        assert result2["skipped_unchanged"] == 2  # Two valid rows skipped

    def test_fingerprints_recomputed_if_missing(self):
        """If fingerprints are missing, they should be recomputed."""
        ctx = _make_context([VALID_ROW.copy()])
        # Don't set row_fingerprints - they should be computed on demand

        result = validate_data(ctx)
        assert result["status"] == "success"
        assert len(ctx.state["row_fingerprints"]) == 1

    def test_fingerprints_recomputed_if_length_mismatch(self):
        """If fingerprint list length doesn't match records, recompute."""
        rows = [
            VALID_ROW.copy(),
            {**VALID_ROW, "employee_id": "EMP002", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        ctx.state["row_fingerprints"] = ["only_one_fp"]  # Wrong length

        result = validate_data(ctx)
        assert result["status"] == "success"
        assert len(ctx.state["row_fingerprints"]) == 2


class TestValidateDataBatching:
    """validate_data caps pending_fixes at FIX_BATCH_SIZE rows and sets total_error_rows."""

    def _make_error_rows(self, count):
        """Create count invalid rows (each with bad dept)."""
        rows = []
        for i in range(count):
            rows.append(
                {
                    **VALID_ROW,
                    "employee_id": f"EMP{i:04d}",
                    "dept": f"BAD{i}",
                    "spend_date": f"2024-01-{(i % 28) + 1:02d}",
                }
            )
        return rows

    def test_caps_at_batch_size(self):
        """When more than FIX_BATCH_SIZE error rows exist, only batch is in pending_fixes."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        validate_data(ctx)
        # pending_fixes should only contain fixes for FIX_BATCH_SIZE rows
        row_indices = {f["row_index"] for f in ctx.state["pending_fixes"]}
        assert len(row_indices) <= FIX_BATCH_SIZE

    def test_sets_total_error_rows(self):
        """total_error_rows reflects the real total, not just the batch."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert ctx.state["total_error_rows"] == 10
        assert result["total_error_rows"] == 10

    def test_batch_size_return_value(self):
        """Return dict includes batch_size."""
        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["batch_size"] == FIX_BATCH_SIZE

    def test_fewer_errors_than_batch(self):
        """When fewer error rows than batch size, all are in pending_fixes."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        result = validate_data(ctx)
        row_indices = {f["row_index"] for f in ctx.state["pending_fixes"]}
        assert len(row_indices) == 3
        assert result["batch_size"] == 3

    def test_skips_skipped_fixes_rows_on_revalidation(self):
        """Rows in skipped_fixes are excluded from re-validation."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        # Simulate row 0 already skipped
        ctx.state["skipped_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD0", "error_message": "Bad"}
        ]
        result = validate_data(ctx)
        # Row 0 should not appear in pending_fixes
        row_indices = {f["row_index"] for f in ctx.state["pending_fixes"]}
        assert 0 not in row_indices
        # Skipped count should include the 1 skipped row
        assert result["skipped_unchanged"] >= 1


class TestWaitingSince:
    """waiting_since is set on errors and cleared on clean validation."""

    def test_set_on_errors(self):
        """waiting_since is set when validation finds errors."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        validate_data(ctx)
        assert ctx.state["waiting_since"] is not None
        assert isinstance(ctx.state["waiting_since"], float)

    def test_cleared_on_clean(self):
        """waiting_since is None when validation succeeds."""
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["waiting_since"] = 12345.0  # Simulate previous value
        validate_data(ctx)
        assert ctx.state["waiting_since"] is None


class TestWaitingSinceResetPerFix:
    """waiting_since resets after each fix/skip when pending fixes remain."""

    def test_write_fix_resets_waiting_since_when_pending_remain(self):
        """write_fix should reset waiting_since when there are still pending fixes."""
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["waiting_since"] = 1000.0  # Old timestamp
        ctx.state["status"] = "WAITING_FOR_USER"

        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # Timer should be reset (new timestamp > old)
        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_write_fix_does_not_set_waiting_since_when_no_pending(self):
        """write_fix should not set waiting_since when all fixes are resolved."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
        ]
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # No pending fixes remain, so waiting_since should NOT be updated
        assert ctx.state["waiting_since"] == 1000.0

    def test_batch_write_fixes_resets_waiting_since_when_pending_remain(self):
        """batch_write_fixes should reset waiting_since when pending fixes remain."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints(rows)
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_batch_write_fixes_does_not_set_waiting_since_when_no_pending(self):
        """batch_write_fixes should not set waiting_since when all fixes resolved."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["waiting_since"] = 1000.0

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        assert ctx.state["waiting_since"] == 1000.0

    def test_skip_row_resets_waiting_since_when_pending_remain(self):
        """skip_row should reset waiting_since when pending fixes remain."""
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}, {**VALID_ROW, "vendor": ""}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["skipped_fixes"] = []
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        skip_row(ctx, row_index=0)

        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_skip_row_does_not_set_waiting_since_when_no_pending(self):
        """skip_row should not set waiting_since when all fixes are resolved."""
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["skipped_fixes"] = []
        ctx.state["waiting_since"] = 1000.0

        skip_row(ctx, row_index=0)

        assert ctx.state["waiting_since"] == 1000.0


class TestSkipRow:
    """skip_row moves fixes from pending_fixes to skipped_fixes."""

    def test_moves_to_skipped_fixes(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        ctx.state["skipped_fixes"] = []
        result = skip_row(ctx, row_index=0)
        assert result["status"] == "skipped"
        assert len(ctx.state["pending_fixes"]) == 0
        assert len(ctx.state["skipped_fixes"]) == 1
        assert ctx.state["skipped_fixes"][0]["row_index"] == 0

    def test_removes_only_target_row(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}, {**VALID_ROW, "vendor": ""}])
        ctx.state["pending_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "BAD",
                "error_message": "Invalid dept",
            },
            {
                "row_index": 1,
                "field": "vendor",
                "current_value": "",
                "error_message": "Empty vendor",
            },
        ]
        ctx.state["skipped_fixes"] = []
        result = skip_row(ctx, row_index=0)
        assert result["remaining_fixes"] == 1
        assert len(ctx.state["pending_fixes"]) == 1
        assert ctx.state["pending_fixes"][0]["row_index"] == 1

    def test_no_op_for_unknown_row(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = []
        ctx.state["skipped_fixes"] = []
        result = skip_row(ctx, row_index=99)
        assert result["status"] == "no_op"

    def test_status_running_when_no_pending(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        ctx.state["skipped_fixes"] = []
        ctx.state["status"] = "WAITING_FOR_USER"
        skip_row(ctx, row_index=0)
        assert ctx.state["status"] == "RUNNING"

    def test_status_fixing_when_pending_remain(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}, {**VALID_ROW, "vendor": ""}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["skipped_fixes"] = []
        skip_row(ctx, row_index=0)
        assert ctx.state["status"] == "FIXING"

    def test_multiple_fixes_per_row(self):
        """All fixes for a row are moved to skipped_fixes."""
        ctx = _make_context([{**VALID_ROW, "dept": "BAD", "vendor": ""}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {
                "row_index": 0,
                "field": "vendor",
                "current_value": "",
                "error_message": "Empty vendor",
            },
        ]
        ctx.state["skipped_fixes"] = []
        result = skip_row(ctx, row_index=0)
        assert len(ctx.state["skipped_fixes"]) == 2
        assert result["remaining_fixes"] == 0


class TestSkipFixes:
    """skip_fixes moves ALL pending to skipped_fixes."""

    def test_moves_all_to_skipped(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["skipped_fixes"] = []
        result = skip_fixes(ctx)
        assert result["status"] == "skipped"
        assert result["skipped_count"] == 2
        assert len(ctx.state["pending_fixes"]) == 0
        assert len(ctx.state["skipped_fixes"]) == 2

    def test_clears_pending(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "X", "error_message": "Bad"},
        ]
        ctx.state["skipped_fixes"] = []
        skip_fixes(ctx)
        assert ctx.state["pending_fixes"] == []

    def test_sets_status_running(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "X", "error_message": "Bad"},
        ]
        ctx.state["skipped_fixes"] = []
        ctx.state["status"] = "WAITING_FOR_USER"
        skip_fixes(ctx)
        assert ctx.state["status"] == "RUNNING"

    def test_sets_validation_complete(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "X", "error_message": "Bad"},
        ]
        ctx.state["skipped_fixes"] = []
        skip_fixes(ctx)
        assert ctx.state["validation_complete"] is True

    def test_clears_waiting_since(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "X", "error_message": "Bad"},
        ]
        ctx.state["skipped_fixes"] = []
        ctx.state["waiting_since"] = 12345.0
        skip_fixes(ctx)
        assert ctx.state["waiting_since"] is None

    def test_no_op_when_empty(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_fixes"] = []
        ctx.state["skipped_fixes"] = []
        result = skip_fixes(ctx)
        assert result["status"] == "no_op"

    def test_appends_to_existing_skipped(self):
        """Existing skipped_fixes are preserved when new ones are added."""
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["skipped_fixes"] = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "X",
                "error_message": "Already skipped",
            },
        ]
        ctx.state["pending_fixes"] = [
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        skip_fixes(ctx)
        assert len(ctx.state["skipped_fixes"]) == 2


class TestBatchWriteFixes:
    """batch_write_fixes applies multi-field fixes to one row."""

    def test_applies_multiple_fields(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG", "vendor": "Acme"})
        assert result["status"] == "fixed"
        assert ctx.state["dataframe_records"][0]["dept"] == "ENG"
        assert ctx.state["dataframe_records"][0]["vendor"] == "Acme"

    def test_removes_matching_pending(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG", "vendor": "Acme"})
        assert result["remaining_fixes"] == 0
        assert len(ctx.state["pending_fixes"]) == 0

    def test_updates_fingerprint(self):
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        fps = compute_all_fingerprints([row])
        ctx.state["row_fingerprints"] = fps
        ctx.state["validated_row_fingerprints"] = {fps[0]: False}
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        old_fp = fps[0]

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        new_fp = ctx.state["row_fingerprints"][0]
        assert old_fp != new_fp
        assert old_fp not in ctx.state["validated_row_fingerprints"]

    def test_partial_fix_leaves_remaining(self):
        """Fixing only some fields of a row leaves unfixed fields in pending."""
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert result["remaining_fixes"] == 1
        assert ctx.state["pending_fixes"][0]["field"] == "vendor"

    def test_status_running_when_no_pending(self):
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["status"] = "WAITING_FOR_USER"

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert ctx.state["status"] == "RUNNING"

    def test_status_fixing_when_pending_remain(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert ctx.state["status"] == "FIXING"

    def test_invalid_row_index(self):
        ctx = _make_context([VALID_ROW.copy()])
        result = batch_write_fixes(ctx, row_index=99, fixes={"dept": "ENG"})
        assert result["status"] == "error"

    def test_empty_fixes_dict(self):
        ctx = _make_context([VALID_ROW.copy()])
        result = batch_write_fixes(ctx, row_index=0, fixes={})
        assert result["status"] == "error"

    def test_string_row_index_coerced(self):
        """String row_index should be coerced to int."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        ctx.state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index="0", fixes={"dept": "ENG"})
        assert result["status"] == "fixed"


class TestRemainingFixesTracking:
    """Tests for remaining_fixes — unbatched errors beyond FIX_BATCH_SIZE."""

    def _make_error_rows(self, count):
        """Create count invalid rows (each with bad dept)."""
        rows = []
        for i in range(count):
            rows.append(
                {
                    **VALID_ROW,
                    "employee_id": f"EMP{i:04d}",
                    "dept": f"BAD{i}",
                    "spend_date": f"2024-01-{(i % 28) + 1:02d}",
                }
            )
        return rows

    def test_remaining_fixes_populated_when_errors_exceed_batch(self):
        """10 error rows → pending has 5 rows, remaining has 5 rows."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        validate_data(ctx)

        pending_rows = {f["row_index"] for f in ctx.state["pending_fixes"]}
        remaining_rows = {f["row_index"] for f in ctx.state["remaining_fixes"]}

        assert len(pending_rows) == FIX_BATCH_SIZE
        assert len(remaining_rows) == 5
        # No overlap between pending and remaining
        assert pending_rows.isdisjoint(remaining_rows)

    def test_remaining_fixes_empty_when_errors_fit_in_batch(self):
        """3 error rows → remaining is empty."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        validate_data(ctx)

        assert len(ctx.state["remaining_fixes"]) == 0
        pending_rows = {f["row_index"] for f in ctx.state["pending_fixes"]}
        assert len(pending_rows) == 3

    def test_remaining_fixes_cleared_on_clean_validation(self):
        """Stale remaining_fixes cleared when validation finds no errors."""
        ctx = _make_context([VALID_ROW.copy()])
        # Simulate stale remaining from a previous run
        ctx.state["remaining_fixes"] = [
            {"row_index": 99, "field": "dept", "current_value": "X", "error_message": "Stale"},
        ]
        validate_data(ctx)

        assert ctx.state["remaining_fixes"] == []

    def test_skip_fixes_includes_remaining(self):
        """skip_fixes moves both pending + remaining to skipped."""
        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        validate_data(ctx)

        pending_count = len(ctx.state["pending_fixes"])
        remaining_count = len(ctx.state["remaining_fixes"])
        assert pending_count > 0
        assert remaining_count > 0

        result = skip_fixes(ctx)

        assert result["status"] == "skipped"
        assert result["skipped_count"] == pending_count + remaining_count
        assert len(ctx.state["pending_fixes"]) == 0
        assert len(ctx.state["remaining_fixes"]) == 0
        assert len(ctx.state["skipped_fixes"]) == pending_count + remaining_count

    def test_skip_fixes_remaining_appear_in_package_errors(self):
        """Full pipeline: validate → skip → package flags all error rows."""
        from app.tools.processing import package_results

        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        validate_data(ctx)

        # All 8 rows should have errors
        assert ctx.state["total_error_rows"] == 8

        # Skip all fixes (pending + remaining)
        skip_fixes(ctx)

        # Package results
        result = package_results(ctx)
        assert result["status"] == "success"
        # All 8 error rows should appear in error_count
        assert result["error_count"] == 8
        assert result["valid_count"] == 0
