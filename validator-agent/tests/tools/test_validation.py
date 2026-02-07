"""Tests for validation tools — updated for new simplified fix cycle algorithm."""

from unittest.mock import MagicMock

from app.fix_utils import FIX_BATCH_SIZE
from app.tools.validation import (
    batch_write_fixes,
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
        "pending_review": [],
        "all_errors": [],
        "skipped_rows": [],
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

    def test_clears_pending_review_on_clean(self):
        ctx = _make_context([VALID_ROW.copy()])
        validate_data(ctx)
        assert ctx.state["pending_review"] == []


class TestValidateDataAutoPopulatesFixes:
    """validate_data auto-populates pending_review when errors found."""

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
        assert result["pending_review_count"] >= 1

    def test_returns_success_with_proceed_action_when_valid(self):
        """Return value must indicate proceed when no errors exist."""
        ctx = _make_context([VALID_ROW.copy()])
        result = validate_data(ctx)
        assert result["status"] == "success"
        assert "Proceed" in result["action"]
        assert result["error_count"] == 0

    def test_populates_pending_review_from_errors(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        validate_data(ctx)
        assert len(ctx.state["pending_review"]) == 1
        fix = ctx.state["pending_review"][0]
        assert fix["row_index"] == 0
        assert fix["field"] == "dept"
        assert fix["current_value"] == "InvalidDept"
        assert "Invalid department" in fix["error_message"]

    def test_multiple_errors_per_row(self):
        row = {**VALID_ROW, "dept": "Bad", "amount": -50}
        ctx = _make_context([row])
        validate_data(ctx)
        fixes = ctx.state["pending_review"]
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
        fixes = ctx.state["pending_review"]
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
        fixes = ctx.state["pending_review"]
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
        fixes = ctx.state["pending_review"]
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


class TestWriteFix:
    """write_fix updates the record and removes from pending_review."""

    def test_updates_record_value(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert ctx.state["dataframe_records"][0]["dept"] == "ENG"

    def test_removes_from_pending_review(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert len(ctx.state["pending_review"]) == 0

    def test_sets_running_when_no_more_fixes(self):
        row = {**VALID_ROW, "dept": "InvalidDept"}
        ctx = _make_context([row])
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert ctx.state["status"] == "RUNNING"

    def test_pops_entire_row_even_with_partial_fix(self):
        """Pop-based: fixing one field pops the entire row. Re-validation catches remaining."""
        row = {**VALID_ROW, "dept": "InvalidDept", "amount": -1}
        ctx = _make_context([row])
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad dept",
            },
            {
                "row_index": 0,
                "field": "amount",
                "current_value": "-1",
                "error_message": "Bad amount",
            },
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        # Entire row is popped — status transitions to RUNNING for re-validation
        assert ctx.state["status"] == "RUNNING"

    def test_stays_waiting_when_other_rows_remain(self):
        """Pop-based: fixing one row leaves other rows in pending_review."""
        rows = [
            {**VALID_ROW, "dept": "InvalidDept"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad dept",
            },
            {
                "row_index": 1,
                "field": "vendor",
                "current_value": "",
                "error_message": "Empty",
            },
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["status"] = "WAITING_FOR_USER"
        write_fix(ctx, row_index=0, field="dept", new_value="ENG")
        assert ctx.state["status"] == "WAITING_FOR_USER"


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

        # Apply fix — need all_errors set by validate_data
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
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)

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
        errors = [
            {
                "row_index": 0,
                "field": "dept",
                "current_value": "InvalidDept",
                "error_message": "Bad",
            }
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)

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
    """validate_data caps pending_review at FIX_BATCH_SIZE rows and populates all_errors."""

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
        """When more than FIX_BATCH_SIZE error rows exist, only batch is in pending_review."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        validate_data(ctx)
        # pending_review should only contain fixes for FIX_BATCH_SIZE rows
        row_indices = {f["row_index"] for f in ctx.state["pending_review"]}
        assert len(row_indices) <= FIX_BATCH_SIZE

    def test_all_errors_has_all_error_rows(self):
        """all_errors reflects the real total, not just the batch."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        validate_data(ctx)
        all_error_rows = {e["row_index"] for e in ctx.state["all_errors"]}
        assert len(all_error_rows) == 10

    def test_batch_size_return_value(self):
        """Return dict includes batch_size."""
        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        result = validate_data(ctx)
        assert result["batch_size"] == FIX_BATCH_SIZE

    def test_fewer_errors_than_batch(self):
        """When fewer error rows than batch size, all are in pending_review."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        result = validate_data(ctx)
        row_indices = {f["row_index"] for f in ctx.state["pending_review"]}
        assert len(row_indices) == 3
        assert result["batch_size"] == 3

    def test_skips_skipped_rows_on_revalidation(self):
        """Rows in skipped_rows are excluded from re-validation."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        # Simulate row 0 already skipped
        ctx.state["skipped_rows"] = [0]
        result = validate_data(ctx)
        # Row 0 should not appear in pending_review
        row_indices = {f["row_index"] for f in ctx.state["pending_review"]}
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
        """write_fix should reset waiting_since when other rows remain in review."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["waiting_since"] = 1000.0  # Old timestamp
        ctx.state["status"] = "WAITING_FOR_USER"

        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # Timer should be reset (new timestamp > old)
        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_write_fix_does_not_set_waiting_since_when_no_pending(self):
        """write_fix should clear waiting_since when all fixes are resolved."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        write_fix(ctx, row_index=0, field="dept", new_value="ENG")

        # No pending review items remain, _pop_from_review sets waiting_since = None
        assert ctx.state["waiting_since"] is None

    def test_batch_write_fixes_resets_waiting_since_when_pending_remain(self):
        """batch_write_fixes should reset waiting_since when other rows remain in review."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints(rows)
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_batch_write_fixes_does_not_set_waiting_since_when_no_pending(self):
        """batch_write_fixes should clear waiting_since when all review items resolved."""
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["waiting_since"] = 1000.0

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        # No pending review items remain, _pop_from_review sets waiting_since = None
        assert ctx.state["waiting_since"] is None

    def test_skip_row_resets_waiting_since_when_pending_remain(self):
        """skip_row should reset waiting_since when pending fixes remain."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        ctx.state["waiting_since"] = 1000.0
        ctx.state["status"] = "WAITING_FOR_USER"

        skip_row(ctx, row_index=0)

        assert ctx.state["waiting_since"] is not None
        assert ctx.state["waiting_since"] > 1000.0

    def test_skip_row_does_not_set_waiting_since_when_no_pending(self):
        """skip_row should clear waiting_since when all fixes are resolved."""
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        ctx.state["waiting_since"] = 1000.0

        skip_row(ctx, row_index=0)

        # No pending review items remain, _pop_from_review sets waiting_since = None
        assert ctx.state["waiting_since"] is None


class TestSkipRow:
    """skip_row adds row index to skipped_rows and pops from pending_review."""

    def test_moves_to_skipped_rows(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        result = skip_row(ctx, row_index=0)
        assert result["status"] == "skipped"
        assert len(ctx.state["pending_review"]) == 0
        assert 0 in ctx.state["skipped_rows"]

    def test_removes_only_target_row(self):
        ctx = _make_context(
            [
                {**VALID_ROW, "dept": "BAD"},
                {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
            ]
        )
        errors = [
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
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        result = skip_row(ctx, row_index=0)
        assert result["remaining_fixes"] == 1
        assert 0 in ctx.state["skipped_rows"]
        assert len(ctx.state["pending_review"]) == 1
        assert ctx.state["pending_review"][0]["row_index"] == 1

    def test_no_op_for_unknown_row(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_review"] = []
        ctx.state["all_errors"] = []
        ctx.state["skipped_rows"] = []
        result = skip_row(ctx, row_index=99)
        assert result["status"] == "no_op"

    def test_status_running_when_no_pending(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        ctx.state["status"] = "WAITING_FOR_USER"
        skip_row(ctx, row_index=0)
        assert ctx.state["status"] == "RUNNING"

    def test_status_waiting_for_user_when_pending_remain(self):
        ctx = _make_context(
            [
                {**VALID_ROW, "dept": "BAD"},
                {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
            ]
        )
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        skip_row(ctx, row_index=0)
        assert ctx.state["status"] == "WAITING_FOR_USER"

    def test_multiple_fixes_per_row(self):
        """All fixes for a row are excluded when that row is skipped."""
        ctx = _make_context([{**VALID_ROW, "dept": "BAD", "vendor": ""}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {
                "row_index": 0,
                "field": "vendor",
                "current_value": "",
                "error_message": "Empty vendor",
            },
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        result = skip_row(ctx, row_index=0)
        assert 0 in ctx.state["skipped_rows"]
        assert result["remaining_fixes"] == 0


class TestSkipFixes:
    """skip_fixes moves ALL pending error rows to skipped_rows."""

    def test_moves_all_to_skipped(self):
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        result = skip_fixes(ctx)
        assert result["status"] == "skipped"
        assert result["skipped_count"] == 2  # 2 unique row indices
        assert len(ctx.state["pending_review"]) == 0
        assert 0 in ctx.state["skipped_rows"]
        assert 1 in ctx.state["skipped_rows"]

    def test_clears_pending(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        skip_fixes(ctx)
        assert ctx.state["pending_review"] == []

    def test_sets_status_running(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        ctx.state["status"] = "WAITING_FOR_USER"
        skip_fixes(ctx)
        assert ctx.state["status"] == "RUNNING"

    def test_clears_waiting_since(self):
        ctx = _make_context([{**VALID_ROW, "dept": "BAD"}])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["skipped_rows"] = []
        ctx.state["waiting_since"] = 12345.0
        skip_fixes(ctx)
        assert ctx.state["waiting_since"] is None

    def test_no_op_when_empty(self):
        ctx = _make_context([VALID_ROW.copy()])
        ctx.state["pending_review"] = []
        ctx.state["all_errors"] = []
        ctx.state["skipped_rows"] = []
        result = skip_fixes(ctx)
        assert result["status"] == "no_op"

    def test_appends_to_existing_skipped(self):
        """Existing skipped_rows are preserved when new ones are added."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        ctx.state["skipped_rows"] = [5]  # Pre-existing skipped row
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        skip_fixes(ctx)
        assert 5 in ctx.state["skipped_rows"]
        assert 0 in ctx.state["skipped_rows"]
        assert 1 in ctx.state["skipped_rows"]


class TestBatchWriteFixes:
    """batch_write_fixes applies multi-field fixes to one row."""

    def test_applies_multiple_fields(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG", "vendor": "Acme"})
        assert result["status"] == "fixed"
        assert ctx.state["dataframe_records"][0]["dept"] == "ENG"
        assert ctx.state["dataframe_records"][0]["vendor"] == "Acme"

    def test_removes_matching_pending(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG", "vendor": "Acme"})
        assert result["remaining_fixes"] == 0
        assert len(ctx.state["pending_review"]) == 0

    def test_updates_fingerprint(self):
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        fps = compute_all_fingerprints([row])
        ctx.state["row_fingerprints"] = fps
        ctx.state["validated_row_fingerprints"] = {fps[0]: False}
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        old_fp = fps[0]

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})

        new_fp = ctx.state["row_fingerprints"][0]
        assert old_fp != new_fp
        assert old_fp not in ctx.state["validated_row_fingerprints"]

    def test_partial_fix_pops_entire_row(self):
        """Pop-based: partial fix pops entire row. Re-validation catches remaining."""
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad dept"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert result["remaining_fixes"] == 0  # Entire row popped
        assert len(ctx.state["pending_review"]) == 0

    def test_status_running_when_no_pending(self):
        row = {**VALID_ROW, "dept": "BAD"}
        ctx = _make_context([row])
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}
        ctx.state["status"] = "WAITING_FOR_USER"

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert ctx.state["status"] == "RUNNING"

    def test_status_waiting_for_user_when_other_rows_remain(self):
        """Pop-based: fixing one row leaves other rows, status stays WAITING_FOR_USER."""
        rows = [
            {**VALID_ROW, "dept": "BAD"},
            {**VALID_ROW, "employee_id": "EMP002", "vendor": "", "spend_date": "2024-01-16"},
        ]
        ctx = _make_context(rows)
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints(rows)
        ctx.state["validated_row_fingerprints"] = {}

        batch_write_fixes(ctx, row_index=0, fixes={"dept": "ENG"})
        assert ctx.state["status"] == "WAITING_FOR_USER"

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
        errors = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        ctx.state["pending_review"] = list(errors)
        ctx.state["all_errors"] = list(errors)
        ctx.state["row_fingerprints"] = compute_all_fingerprints([row])
        ctx.state["validated_row_fingerprints"] = {}

        result = batch_write_fixes(ctx, row_index="0", fixes={"dept": "ENG"})
        assert result["status"] == "fixed"


class TestRemainingFixesTracking:
    """Tests for all_errors — all errors tracked, pending_review batched by row."""

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
        """10 error rows -> all_errors has 10 rows, pending_review has FIX_BATCH_SIZE rows."""
        rows = self._make_error_rows(10)
        ctx = _make_context(rows)
        validate_data(ctx)

        all_error_rows = {e["row_index"] for e in ctx.state["all_errors"]}
        pending_rows = {f["row_index"] for f in ctx.state["pending_review"]}

        assert len(all_error_rows) == 10
        assert len(pending_rows) == FIX_BATCH_SIZE

    def test_remaining_fixes_empty_when_errors_fit_in_batch(self):
        """3 error rows -> all_errors and pending_review both have 3 rows."""
        rows = self._make_error_rows(3)
        ctx = _make_context(rows)
        validate_data(ctx)

        all_error_rows = {e["row_index"] for e in ctx.state["all_errors"]}
        pending_rows = {f["row_index"] for f in ctx.state["pending_review"]}
        assert len(all_error_rows) == 3
        assert len(pending_rows) == 3

    def test_remaining_fixes_cleared_on_clean_validation(self):
        """Stale all_errors cleared when validation finds no errors."""
        ctx = _make_context([VALID_ROW.copy()])
        # Simulate stale errors from a previous run
        ctx.state["all_errors"] = [
            {"row_index": 99, "field": "dept", "current_value": "X", "error_message": "Stale"},
        ]
        validate_data(ctx)

        assert ctx.state["all_errors"] == []

    def test_skip_fixes_includes_remaining(self):
        """skip_fixes marks all active error row indices as skipped."""
        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        validate_data(ctx)

        # All 8 rows have errors in all_errors
        all_error_rows = {e["row_index"] for e in ctx.state["all_errors"]}
        assert len(all_error_rows) == 8

        result = skip_fixes(ctx)

        assert result["status"] == "skipped"
        # All 8 error rows should be in skipped_rows
        assert len(ctx.state["skipped_rows"]) == 8
        assert len(ctx.state["pending_review"]) == 0

    def test_skip_fixes_remaining_appear_in_package_errors(self):
        """Full pipeline: validate -> skip -> package flags all error rows."""
        from app.tools.processing import package_results

        rows = self._make_error_rows(8)
        ctx = _make_context(rows)
        validate_data(ctx)

        # All 8 rows should have errors in all_errors
        all_error_rows = {e["row_index"] for e in ctx.state["all_errors"]}
        assert len(all_error_rows) == 8

        # Skip all fixes
        skip_fixes(ctx)

        # Package results
        result = package_results(ctx)
        assert result["status"] == "success"
        # All 8 error rows should appear in error_count
        assert result["error_count"] == 8
        assert result["valid_count"] == 0
