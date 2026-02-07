"""Tests for app.fix_utils — pure fix-application functions."""

from app.fix_utils import apply_batch_fixes, apply_single_fix, apply_skip_all, apply_skip_row
from app.utils import compute_all_fingerprints, compute_row_fingerprint

VALID_ROW = {
    "employee_id": "EMP001",
    "dept": "ENG",
    "amount": 1500.00,
    "currency": "USD",
    "spend_date": "2024-01-15",
    "vendor": "Acme Corp",
    "fx_rate": 1.0,
}


def _make_state(records, **extra):
    """Build a minimal session state dict."""
    columns = list(records[0].keys()) if records else []
    return {
        "dataframe_records": records,
        "dataframe_columns": columns,
        "pending_fixes": [],
        "skipped_fixes": [],
        "remaining_fixes": [],
        "status": "WAITING_FOR_USER",
        **extra,
    }


class TestApplySingleFix:
    """apply_single_fix updates one cell and removes matching pending fix."""

    def test_updates_record_value(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        result = apply_single_fix(state, 0, "dept", "ENG")
        assert result["status"] == "fixed"
        assert state["dataframe_records"][0]["dept"] == "ENG"

    def test_removes_matching_pending_fix(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        apply_single_fix(state, 0, "dept", "ENG")
        assert len(state["pending_fixes"]) == 0

    def test_status_running_when_no_pending(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        apply_single_fix(state, 0, "dept", "ENG")
        assert state["status"] == "RUNNING"

    def test_status_fixing_when_pending_remain(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 0, "field": "amount", "current_value": "-1", "error_message": "Bad"},
        ]
        apply_single_fix(state, 0, "dept", "ENG")
        assert state["status"] == "FIXING"

    def test_out_of_range_row_index(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_single_fix(state, 99, "dept", "ENG")
        assert result["status"] == "error"

    def test_negative_row_index(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_single_fix(state, -1, "dept", "ENG")
        assert result["status"] == "error"

    def test_invalid_row_index_type(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_single_fix(state, "abc", "dept", "ENG")
        assert result["status"] == "error"

    def test_string_row_index_coerced(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        result = apply_single_fix(state, "0", "dept", "ENG")
        assert result["status"] == "fixed"

    def test_updates_fingerprint(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["row_fingerprints"] = compute_all_fingerprints([row])
        state["validated_row_fingerprints"] = {}
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        old_fp = state["row_fingerprints"][0]

        apply_single_fix(state, 0, "dept", "ENG")

        new_fp = state["row_fingerprints"][0]
        assert old_fp != new_fp
        assert new_fp == compute_row_fingerprint(state["dataframe_records"][0])

    def test_invalidates_old_fingerprint(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        fps = compute_all_fingerprints([row])
        state["row_fingerprints"] = fps
        state["validated_row_fingerprints"] = {fps[0]: False}
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        old_fp = fps[0]

        apply_single_fix(state, 0, "dept", "ENG")

        assert old_fp not in state["validated_row_fingerprints"]

    def test_returns_old_and_new_value(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        result = apply_single_fix(state, 0, "dept", "ENG")
        assert result["old_value"] == "BAD"
        assert result["new_value"] == "ENG"


class TestApplyBatchFixes:
    """apply_batch_fixes applies multiple fields to one row."""

    def test_applies_multiple_fields(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        state["row_fingerprints"] = compute_all_fingerprints([row])
        state["validated_row_fingerprints"] = {}

        result = apply_batch_fixes(state, 0, {"dept": "ENG", "vendor": "Acme"})
        assert result["status"] == "fixed"
        assert state["dataframe_records"][0]["dept"] == "ENG"
        assert state["dataframe_records"][0]["vendor"] == "Acme"

    def test_removes_matching_pending(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        state["row_fingerprints"] = compute_all_fingerprints([row])
        state["validated_row_fingerprints"] = {}

        result = apply_batch_fixes(state, 0, {"dept": "ENG", "vendor": "Acme"})
        assert result["remaining_fixes"] == 0

    def test_out_of_range(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_batch_fixes(state, 99, {"dept": "ENG"})
        assert result["status"] == "error"

    def test_empty_fixes(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_batch_fixes(state, 0, {})
        assert result["status"] == "error"

    def test_non_dict_fixes(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_batch_fixes(state, 0, "not a dict")
        assert result["status"] == "error"

    def test_partial_fix_leaves_remaining(self):
        row = {**VALID_ROW, "dept": "BAD", "vendor": ""}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 0, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        state["row_fingerprints"] = compute_all_fingerprints([row])
        state["validated_row_fingerprints"] = {}

        result = apply_batch_fixes(state, 0, {"dept": "ENG"})
        assert result["remaining_fixes"] == 1

    def test_status_running_when_no_pending(self):
        row = {**VALID_ROW, "dept": "BAD"}
        state = _make_state([row])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        state["row_fingerprints"] = compute_all_fingerprints([row])
        state["validated_row_fingerprints"] = {}

        apply_batch_fixes(state, 0, {"dept": "ENG"})
        assert state["status"] == "RUNNING"


class TestApplySkipRow:
    """apply_skip_row moves row fixes from pending to skipped."""

    def test_moves_to_skipped(self):
        state = _make_state([{**VALID_ROW, "dept": "BAD"}])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        result = apply_skip_row(state, 0)
        assert result["status"] == "skipped"
        assert len(state["pending_fixes"]) == 0
        assert len(state["skipped_fixes"]) == 1

    def test_no_op_for_unknown_row(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_skip_row(state, 99)
        assert result["status"] == "no_op"

    def test_removes_only_target_row(self):
        state = _make_state([{**VALID_ROW, "dept": "BAD"}, {**VALID_ROW, "vendor": ""}])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        result = apply_skip_row(state, 0)
        assert result["remaining_fixes"] == 1
        assert state["pending_fixes"][0]["row_index"] == 1

    def test_status_running_when_no_pending(self):
        state = _make_state([{**VALID_ROW, "dept": "BAD"}])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
        ]
        apply_skip_row(state, 0)
        assert state["status"] == "RUNNING"

    def test_status_fixing_when_pending_remain(self):
        state = _make_state([{**VALID_ROW, "dept": "BAD"}, {**VALID_ROW, "vendor": ""}])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        apply_skip_row(state, 0)
        assert state["status"] == "FIXING"

    def test_invalid_row_index_type(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_skip_row(state, "abc")
        assert result["status"] == "error"


class TestApplySkipAll:
    """apply_skip_all moves all pending + remaining to skipped."""

    def test_moves_all_to_skipped(self):
        state = _make_state([VALID_ROW.copy()])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Invalid"},
            {"row_index": 1, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        result = apply_skip_all(state)
        assert result["status"] == "skipped"
        assert result["skipped_count"] == 2
        assert len(state["pending_fixes"]) == 0
        assert len(state["skipped_fixes"]) == 2

    def test_includes_remaining_fixes(self):
        state = _make_state([VALID_ROW.copy()])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        state["remaining_fixes"] = [
            {"row_index": 5, "field": "vendor", "current_value": "", "error_message": "Empty"},
        ]
        result = apply_skip_all(state)
        assert result["skipped_count"] == 2
        assert len(state["remaining_fixes"]) == 0

    def test_sets_status_running(self):
        state = _make_state([VALID_ROW.copy()])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        apply_skip_all(state)
        assert state["status"] == "RUNNING"

    def test_sets_validation_complete(self):
        state = _make_state([VALID_ROW.copy()])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        apply_skip_all(state)
        assert state["validation_complete"] is True

    def test_clears_waiting_since(self):
        state = _make_state([VALID_ROW.copy()])
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        state["waiting_since"] = 12345.0
        apply_skip_all(state)
        assert state["waiting_since"] is None

    def test_no_op_when_empty(self):
        state = _make_state([VALID_ROW.copy()])
        result = apply_skip_all(state)
        assert result["status"] == "no_op"

    def test_appends_to_existing_skipped(self):
        state = _make_state([VALID_ROW.copy()])
        state["skipped_fixes"] = [
            {"row_index": 9, "field": "x", "current_value": "y", "error_message": "Already"},
        ]
        state["pending_fixes"] = [
            {"row_index": 0, "field": "dept", "current_value": "BAD", "error_message": "Bad"},
        ]
        apply_skip_all(state)
        assert len(state["skipped_fixes"]) == 2
