"""Tests for processing tools — Story 2.3."""

import base64
import io
from unittest.mock import MagicMock

import pandas as pd

from app.tools.processing import (
    DEFAULT_COST_CENTER_MAP,
    auto_add_computed_columns,
    package_results,
    transform_data,
)


def _make_context(records: list[dict], **extra_state) -> MagicMock:
    """Helper to create a mock tool context with state."""
    ctx = MagicMock()
    columns = list(records[0].keys()) if records else []
    ctx.state = {
        "dataframe_records": records,
        "dataframe_columns": columns,
        "pending_review": [],
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
    """package_results creates success.xlsx and errors.xlsx as base64 in state."""

    def test_separates_valid_and_invalid(self):
        row_valid = SAMPLE_ROW.copy()
        row_invalid = {**SAMPLE_ROW, "employee_id": "EMP002"}
        ctx = _make_context([row_valid, row_invalid])
        ctx.state["skipped_rows"] = [1]
        ctx.state["all_errors"] = [
            {
                "row_index": 1,
                "field": "dept",
                "current_value": "Engineering",
                "error_message": "bad",
            }
        ]

        result = package_results(ctx)
        assert result["status"] == "success"
        assert "success.xlsx" in ctx.state["artifacts"]
        assert "errors.xlsx" in ctx.state["artifacts"]

    def test_sets_completed_status(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        package_results(ctx)
        assert ctx.state["status"] == "COMPLETED"

    def test_artifacts_in_state(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        package_results(ctx)
        assert "success.xlsx" in ctx.state["artifacts"]
        assert "errors.xlsx" in ctx.state["artifacts"]

    def test_artifacts_have_base64_data(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        package_results(ctx)
        for name in ("success.xlsx", "errors.xlsx"):
            info = ctx.state["artifacts"][name]
            assert isinstance(info, dict)
            assert "data" in info
            assert "mime_type" in info
            # Verify base64 is decodable
            raw = base64.b64decode(info["data"])
            assert len(raw) > 0

    def test_success_artifact_is_valid_excel(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        package_results(ctx)

        info = ctx.state["artifacts"]["success.xlsx"]
        excel_bytes = base64.b64decode(info["data"])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert len(df) == 1
        assert "employee_id" in df.columns

    def test_errors_artifact_has_errors_column(self):
        row_invalid = {**SAMPLE_ROW, "employee_id": "BAD"}
        ctx = _make_context([row_invalid])
        ctx.state["skipped_rows"] = [0]
        ctx.state["all_errors"] = [
            {
                "row_index": 0,
                "field": "employee_id",
                "current_value": "BAD",
                "error_message": "Bad ID",
            }
        ]

        package_results(ctx)

        info = ctx.state["artifacts"]["errors.xlsx"]
        excel_bytes = base64.b64decode(info["data"])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert "error_reason" in df.columns

    def test_rejects_when_waiting_for_user(self):
        """Guard: package_results must reject if status is WAITING_FOR_USER.

        This prevents the agent from skipping the correction loop and packaging
        results before the user has had a chance to fix validation errors.
        """
        ctx = _make_context([SAMPLE_ROW.copy()])
        ctx.state["status"] = "WAITING_FOR_USER"
        ctx.state["pending_review"] = [
            {"row_index": 0, "field": "dept", "current_value": "Bad", "error_message": "Invalid"}
        ]

        result = package_results(ctx)

        assert result["status"] == "error"
        assert "WAITING_FOR_USER" in result["message"]
        # Status should remain unchanged - not set to PACKAGING or COMPLETED
        assert ctx.state["status"] == "WAITING_FOR_USER"
        # No artifacts should be created
        assert ctx.state["artifacts"] == {}

    def test_rejects_when_pending_review_exist(self):
        """Guard: package_results must reject if pending_review are non-empty even if status is not WAITING_FOR_USER."""
        ctx = _make_context([SAMPLE_ROW.copy()])
        ctx.state["status"] = "RUNNING"
        ctx.state["pending_review"] = [
            {"row_index": 0, "field": "dept", "current_value": "Bad", "error_message": "Invalid"}
        ]

        result = package_results(ctx)

        assert result["status"] == "error"
        assert ctx.state["artifacts"] == {}


class TestPackageWithSkippedFixes:
    """package_results uses skipped_fixes for error rows and includes error_reason."""

    def test_skipped_fixes_become_error_rows(self):
        row_valid = SAMPLE_ROW.copy()
        row_skipped = {**SAMPLE_ROW, "employee_id": "EMP002"}
        ctx = _make_context([row_valid, row_skipped])
        ctx.state["skipped_rows"] = [1]
        ctx.state["all_errors"] = [
            {
                "row_index": 1,
                "field": "dept",
                "current_value": "Engineering",
                "error_message": "Invalid dept",
            },
        ]

        result = package_results(ctx)
        assert result["status"] == "success"
        assert result["valid_count"] == 1
        assert result["error_count"] == 1

        # Check errors.xlsx has _errors column with reason
        errors_info = ctx.state["artifacts"]["errors.xlsx"]
        errors_bytes = base64.b64decode(errors_info["data"])
        df = pd.read_excel(io.BytesIO(errors_bytes))
        assert "error_reason" in df.columns
        assert "Invalid dept" in df["error_reason"].iloc[0]

    def test_no_skipped_fixes_all_valid(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        ctx.state["skipped_rows"] = []
        ctx.state["all_errors"] = []
        result = package_results(ctx)
        assert result["valid_count"] == 1
        assert result["error_count"] == 0


class TestTransformDataLookupMap:
    """transform_data with lookup_map derives values from a mapping dict."""

    LOOKUP_MAP = {"FIN": "CC-100", "HR": "CC-200", "ENG": "CC-300"}

    def _rows(self):
        return [
            {**SAMPLE_ROW, "dept": "FIN"},
            {**SAMPLE_ROW, "dept": "HR", "employee_id": "EMP002"},
            {**SAMPLE_ROW, "dept": "ENG", "employee_id": "EMP003"},
        ]

    def test_lookup_maps_values(self):
        ctx = _make_context(self._rows())
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=self.LOOKUP_MAP,
        )
        assert result["status"] == "success"
        records = ctx.state["dataframe_records"]
        assert records[0]["cost_center"] == "CC-100"
        assert records[1]["cost_center"] == "CC-200"
        assert records[2]["cost_center"] == "CC-300"

    def test_unmapped_value_default(self):
        rows = [{**SAMPLE_ROW, "dept": "UNKNOWN_DEPT"}]
        ctx = _make_context(rows)
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=self.LOOKUP_MAP,
        )
        assert result["status"] == "success"
        assert ctx.state["dataframe_records"][0]["cost_center"] == "UNMAPPED"

    def test_unmapped_value_custom(self):
        rows = [{**SAMPLE_ROW, "dept": "UNKNOWN_DEPT"}]
        ctx = _make_context(rows)
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=self.LOOKUP_MAP,
            unmapped_value="N/A",
        )
        assert result["status"] == "success"
        assert ctx.state["dataframe_records"][0]["cost_center"] == "N/A"

    def test_empty_map_all_unmapped(self):
        rows = [{**SAMPLE_ROW, "dept": "FIN"}]
        ctx = _make_context(rows)
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map={},
        )
        assert result["status"] == "success"
        assert ctx.state["dataframe_records"][0]["cost_center"] == "UNMAPPED"

    def test_missing_lookup_field_returns_error(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_map=self.LOOKUP_MAP,
        )
        assert result["status"] == "error"

    def test_missing_lookup_map_returns_error(self):
        ctx = _make_context([SAMPLE_ROW.copy()])
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
        )
        assert result["status"] == "error"

    def test_updates_columns_list(self):
        ctx = _make_context(self._rows())
        transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=self.LOOKUP_MAP,
        )
        assert "cost_center" in ctx.state["dataframe_columns"]

    def test_lookup_field_missing_in_row(self):
        rows = [{"employee_id": "EMP001", "amount": 100}]  # no "dept" key
        ctx = _make_context(rows)
        result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=self.LOOKUP_MAP,
        )
        assert result["status"] == "success"
        assert ctx.state["dataframe_records"][0]["cost_center"] == "UNMAPPED"


class TestAutoAddComputedColumns:
    """auto_add_computed_columns adds amount_usd, cost_center, approval_required."""

    def test_adds_amount_usd(self):
        records = [{"amount": 100.0, "fx_rate": 1.1, "dept": "ENG"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["amount_usd"] == 110.0

    def test_amount_usd_defaults_fx_rate_to_1(self):
        records = [{"amount": 250.0, "dept": "HR"}]
        columns = ["amount", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["amount_usd"] == 250.0

    def test_amount_usd_defaults_amount_to_0(self):
        records = [{"dept": "HR", "fx_rate": 1.5}]
        columns = ["dept", "fx_rate"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["amount_usd"] == 0.0

    def test_adds_cost_center_with_default_map(self):
        records = [
            {"amount": 100, "fx_rate": 1.0, "dept": "FIN"},
            {"amount": 100, "fx_rate": 1.0, "dept": "ENG"},
        ]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["cost_center"] == "100"
        assert records[1]["cost_center"] == "300"

    def test_cost_center_uses_frontend_map(self):
        """Frontend map merged on top of defaults."""
        records = [{"amount": 100, "fx_rate": 1.0, "dept": "FIN"}]
        columns = ["amount", "fx_rate", "dept"]
        state = {"globals": {"cost_center_map": {"FIN": "CUSTOM-100"}}}
        auto_add_computed_columns(records, columns, state)
        assert records[0]["cost_center"] == "CUSTOM-100"

    def test_cost_center_unmapped_dept(self):
        records = [{"amount": 100, "fx_rate": 1.0, "dept": "UNKNOWN"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["cost_center"] == "UNMAPPED"

    def test_approval_required_yes(self):
        records = [{"amount": 60000, "fx_rate": 1.0, "dept": "FIN"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["approval_required"] == "YES"

    def test_approval_required_no_under_threshold(self):
        records = [{"amount": 50000, "fx_rate": 1.0, "dept": "FIN"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["approval_required"] == "NO"

    def test_approval_required_no_non_fin(self):
        records = [{"amount": 99999, "fx_rate": 1.0, "dept": "ENG"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        assert records[0]["approval_required"] == "NO"

    def test_all_three_columns_added(self):
        records = [
            {"amount": 1000, "fx_rate": 1.1, "dept": "FIN"},
            {"amount": 2000, "fx_rate": 0.9, "dept": "HR"},
        ]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        for r in records:
            assert "amount_usd" in r
            assert "cost_center" in r
            assert "approval_required" in r
        assert "amount_usd" in columns
        assert "cost_center" in columns
        assert "approval_required" in columns

    def test_idempotent_columns_list(self):
        records = [{"amount": 100, "fx_rate": 1.0, "dept": "ENG"}]
        columns = ["amount", "fx_rate", "dept"]
        auto_add_computed_columns(records, columns, {})
        auto_add_computed_columns(records, columns, {})
        assert columns.count("amount_usd") == 1
        assert columns.count("cost_center") == 1
        assert columns.count("approval_required") == 1

    def test_default_cost_center_map_covers_all_depts(self):
        for dept in ["FIN", "HR", "ENG", "OPS"]:
            assert dept in DEFAULT_COST_CENTER_MAP


class TestPackageResultsComputedColumns:
    """package_results automatically adds computed columns."""

    def test_package_includes_computed_columns(self):
        rows = [
            {
                "employee_id": "EMP001",
                "dept": "ENG",
                "amount": 1500.0,
                "currency": "USD",
                "spend_date": "2024-01-15",
                "vendor": "Acme Corp",
                "fx_rate": 1.0,
            }
        ]
        ctx = _make_context(rows)
        package_results(ctx)

        info = ctx.state["artifacts"]["success.xlsx"]
        excel_bytes = base64.b64decode(info["data"])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert "amount_usd" in df.columns
        assert "cost_center" in df.columns
        assert "approval_required" in df.columns

    def test_package_approval_required_values(self):
        rows = [
            {
                "employee_id": "EMP001",
                "dept": "FIN",
                "amount": 60000.0,
                "currency": "USD",
                "spend_date": "2024-01-15",
                "vendor": "Acme Corp",
                "fx_rate": 1.0,
            },
            {
                "employee_id": "EMP002",
                "dept": "FIN",
                "amount": 1000.0,
                "currency": "USD",
                "spend_date": "2024-01-16",
                "vendor": "Beta Inc",
                "fx_rate": 1.0,
            },
        ]
        ctx = _make_context(rows)
        package_results(ctx)

        info = ctx.state["artifacts"]["success.xlsx"]
        excel_bytes = base64.b64decode(info["data"])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert df["approval_required"].iloc[0] == "YES"
        assert df["approval_required"].iloc[1] == "NO"

    def test_package_with_frontend_cost_center_map(self):
        rows = [
            {
                "employee_id": "EMP001",
                "dept": "ENG",
                "amount": 1500.0,
                "currency": "USD",
                "spend_date": "2024-01-15",
                "vendor": "Acme Corp",
                "fx_rate": 1.0,
            }
        ]
        ctx = _make_context(rows)
        ctx.state["globals"] = {"cost_center_map": {"ENG": "CUSTOM-ENG"}}
        package_results(ctx)

        info = ctx.state["artifacts"]["success.xlsx"]
        excel_bytes = base64.b64decode(info["data"])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        assert df["cost_center"].iloc[0] == "CUSTOM-ENG"
