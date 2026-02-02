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
        await package_results(ctx)
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
