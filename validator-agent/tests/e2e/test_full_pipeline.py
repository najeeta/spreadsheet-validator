"""End-to-end integration test: full pipeline — Story 6.1."""

import base64
import io
import pathlib

import pandas as pd
import pytest
import httpx

from app.server import fastapi_app

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client():
    """Create an async test client for the FastAPI app."""
    transport = httpx.ASGITransport(app=fastapi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ── Test CSV with valid and invalid rows ─────────────────────────────────
# Updated to match new validation rules:
# - dept: FIN, HR, ENG, OPS only
# - currency: USD, EUR, GBP, INR only
# - employee_id: 4-12 alphanumeric chars
MIXED_CSV = """employee_id,dept,amount,currency,spend_date,vendor,fx_rate
EMP001,ENG,1500.00,USD,2024-01-15,Acme Corp,1.0
EMP002,HR,2500.50,EUR,2024-02-20,Beta Inc,1.08
BAD,BadDept,-100,XYZ,01/15/2024,,0.01
EMP003,OPS,750.00,GBP,2024-03-10,Gamma Ltd,1.27
"""


class TestFullPipeline:
    """Full pipeline: session -> upload -> ingest -> validate -> transform -> package."""

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Step 1: Create a session via POST /run."""
        async with client as c:
            resp = await c.post("/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        """Step 2: Upload a CSV via POST /upload (simplified - no state updates)."""
        async with client as c:
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]

            files = {"file": ("mixed.csv", io.BytesIO(MIXED_CSV.encode()), "text/csv")}
            resp = await c.post(
                "/upload",
                data={"session_id": session_id},
                files=files,
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_upload_saves_artifact(self, client):
        """Step 3: Verify file is saved as artifact (not in session state)."""
        async with client as c:
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]

            files = {"file": ("test.csv", io.BytesIO(MIXED_CSV.encode()), "text/csv")}
            upload_resp = await c.post(
                "/upload",
                data={"session_id": session_id},
                files=files,
            )
            assert upload_resp.json()["file_name"] == "test.csv"

            # Verify artifact is downloadable
            artifact_resp = await c.get("/artifacts/test.csv")
        assert artifact_resp.status_code == 200
        assert artifact_resp.content.decode().startswith("employee_id")

    @pytest.mark.asyncio
    async def test_upload_does_not_populate_state(self, client):
        """Step 3b: Verify upload does NOT populate state (parsing deferred to agent)."""
        async with client as c:
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]

            files = {"file": ("data.csv", io.BytesIO(MIXED_CSV.encode()), "text/csv")}
            await c.post(
                "/upload",
                data={"session_id": session_id},
                files=files,
            )

            detail_resp = await c.get(f"/runs/{session_id}")
        data = detail_resp.json()
        # Simplified upload does NOT populate these fields
        assert "uploaded_file" not in data
        assert "dataframe_records" not in data or len(data.get("dataframe_records", [])) == 0


class TestToolChainDirect:
    """Test tool chain directly (no LLM) to verify data flow."""

    def test_full_tool_chain(self):
        """Call tools in sequence: ingest -> validate -> transform -> package."""
        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results, transform_data
        from app.tools.validation import validate_data

        # Use the test fixture CSV
        csv_path = str(FIXTURES / "test_data.csv")

        # Step 1: Ingest
        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        ingest_result = ingest_file(ctx, file_path=csv_path)
        assert ingest_result["status"] == "success"
        assert ingest_result["row_count"] == 3
        assert ctx.state["status"] == "RUNNING"

        # Step 2: Validate
        validate_result = validate_data(ctx)
        assert validate_result["status"] == "success"
        assert ctx.state["status"] == "VALIDATING"

        # Step 3: Transform — add amount_usd column
        transform_result = transform_data(
            ctx,
            new_column_name="amount_usd",
            expression="round(row['amount'] * row['fx_rate'], 2)",
        )
        assert transform_result["status"] == "success"
        assert "amount_usd" in ctx.state["dataframe_columns"]
        assert ctx.state["status"] == "TRANSFORMING"

        # Verify computed values
        for record in ctx.state["dataframe_records"]:
            expected = round(record["amount"] * record["fx_rate"], 2)
            assert record["amount_usd"] == expected

        # Step 4: Package — stores base64 artifacts in state
        package_result = package_results(ctx)
        assert package_result["status"] == "success"
        assert ctx.state["status"] == "COMPLETED"
        assert "success.xlsx" in ctx.state["artifacts"]
        assert "errors.xlsx" in ctx.state["artifacts"]

        # Verify success.xlsx is valid Excel (base64-decoded)
        success_info = ctx.state["artifacts"]["success.xlsx"]
        success_bytes = base64.b64decode(success_info["data"])
        df_success = pd.read_excel(io.BytesIO(success_bytes))
        assert len(df_success) > 0
        assert "amount_usd" in df_success.columns

    def test_tool_chain_with_errors(self):
        """Tool chain with invalid data: validate -> skip_fixes -> package."""
        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results
        from app.tools.validation import skip_fixes, validate_data

        # Create a temp CSV with invalid data
        import tempfile

        csv_content = MIXED_CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name

        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "skipped_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        # Ingest
        ingest_result = ingest_file(ctx, file_path=tmp_path)
        assert ingest_result["status"] == "success"
        assert ingest_result["row_count"] == 4

        # Validate — should find errors and auto-populate pending_fixes
        validate_result = validate_data(ctx)
        assert validate_result["error_count"] > 0
        assert validate_result["status"] == "waiting_for_fixes"
        assert ctx.state["status"] == "WAITING_FOR_USER"
        assert len(ctx.state["pending_fixes"]) > 0

        # Guard: package_results should reject while WAITING_FOR_USER
        guard_result = package_results(ctx)
        assert guard_result["status"] == "error"
        assert "WAITING_FOR_USER" in guard_result["message"]

        # Simulate user choosing to skip all fixes
        skip_result = skip_fixes(ctx)
        assert skip_result["status"] == "skipped"
        assert ctx.state["status"] == "RUNNING"
        assert len(ctx.state["skipped_fixes"]) > 0

        # Package — should now separate valid and invalid using skipped_fixes
        package_result = package_results(ctx)

        assert package_result["valid_count"] > 0
        assert package_result["error_count"] > 0
        assert ctx.state["status"] == "COMPLETED"

        # Verify errors.xlsx has _errors column (base64-decoded)
        errors_info = ctx.state["artifacts"]["errors.xlsx"]
        errors_bytes = base64.b64decode(errors_info["data"])
        df_errors = pd.read_excel(io.BytesIO(errors_bytes))
        assert "error_reason" in df_errors.columns
        assert len(df_errors) > 0

        # Clean up
        import os

        os.unlink(tmp_path)

    def test_tool_chain_with_cost_center(self):
        """Full chain with cost_center lookup: ingest -> validate -> transform (lookup) -> package.

        Note: auto_add_computed_columns in package_results overwrites cost_center
        with DEFAULT_COST_CENTER_MAP values, so the lookup_map values here must match
        the defaults for consistency.
        """
        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results, transform_data
        from app.tools.validation import validate_data

        csv_path = str(FIXTURES / "test_data.csv")

        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        # Step 1: Ingest
        ingest_result = ingest_file(ctx, file_path=csv_path)
        assert ingest_result["status"] == "success"

        # Step 2: Validate
        validate_data(ctx)

        # Step 3: Transform — add cost_center via lookup map (matching defaults)
        cost_center_map = {"ENG": "300", "HR": "200", "OPS": "400"}
        transform_result = transform_data(
            ctx,
            new_column_name="cost_center",
            lookup_field="dept",
            lookup_map=cost_center_map,
        )
        assert transform_result["status"] == "success"
        assert "cost_center" in ctx.state["dataframe_columns"]

        # Verify mapped values
        for record in ctx.state["dataframe_records"]:
            assert record["cost_center"] == cost_center_map[record["dept"]]

        # Step 4: Package
        package_result = package_results(ctx)
        assert package_result["status"] == "success"

        # Verify cost_center column in success.xlsx
        success_info = ctx.state["artifacts"]["success.xlsx"]
        success_bytes = base64.b64decode(success_info["data"])
        df_success = pd.read_excel(io.BytesIO(success_bytes))
        assert "cost_center" in df_success.columns

    def test_full_tool_chain_includes_computed_columns(self):
        """Ingest -> Validate -> Package (no explicit transform_data call).

        auto_add_computed_columns should add amount_usd, cost_center, approval_required
        automatically during packaging.
        """
        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results
        from app.tools.validation import validate_data

        csv_path = str(FIXTURES / "test_data.csv")

        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        # Ingest
        ingest_result = ingest_file(ctx, file_path=csv_path)
        assert ingest_result["status"] == "success"

        # Validate
        validate_result = validate_data(ctx)
        assert validate_result["status"] == "success"

        # Package — no transform_data call
        package_result = package_results(ctx)
        assert package_result["status"] == "success"

        # Verify computed columns in success.xlsx
        success_info = ctx.state["artifacts"]["success.xlsx"]
        success_bytes = base64.b64decode(success_info["data"])
        df = pd.read_excel(io.BytesIO(success_bytes))
        assert "amount_usd" in df.columns
        assert "cost_center" in df.columns
        assert "approval_required" in df.columns

        # Verify amount_usd values
        for _, row in df.iterrows():
            expected = round(float(row["amount"]) * float(row["fx_rate"]), 2)
            assert row["amount_usd"] == expected


class TestFixLoopE2E:
    """E2E tests for the fix-loop: skip_row, skip_fixes, batch_write_fixes."""

    def _setup_ctx_with_errors(self, csv_content=None):
        """Set up a context with ingested data containing errors."""
        import tempfile

        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.validation import validate_data

        csv = csv_content or MIXED_CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv)
            tmp_path = f.name

        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "skipped_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        ingest_file(ctx, file_path=tmp_path)
        validate_data(ctx)

        import os

        os.unlink(tmp_path)
        return ctx

    def test_skip_row_then_revalidate_then_package(self):
        """validate -> skip_row -> re-validate -> package."""
        from app.tools.processing import package_results
        from app.tools.validation import skip_fixes, skip_row

        ctx = self._setup_ctx_with_errors()
        assert ctx.state["status"] == "WAITING_FOR_USER"
        assert len(ctx.state["pending_fixes"]) > 0

        # Skip the first error row
        first_row_idx = ctx.state["pending_fixes"][0]["row_index"]
        skip_row(ctx, row_index=first_row_idx)

        # Skip all remaining
        if ctx.state["pending_fixes"]:
            skip_fixes(ctx)

        # Package
        result = package_results(ctx)
        assert result["status"] == "success"
        assert result["error_count"] > 0

    def test_batch_fix_all_then_revalidate_clean(self):
        """validate -> batch_fix all errors -> re-validate -> clean -> package."""
        from app.tools.processing import package_results
        from app.tools.validation import batch_write_fixes, validate_data

        # Use a CSV with a single fixable error
        csv_fixable = """employee_id,dept,amount,currency,spend_date,vendor,fx_rate
EMP001,ENG,1500.00,USD,2024-01-15,Acme Corp,1.0
EMP002,SALES,2500.50,USD,2024-02-20,Beta Inc,1.0
"""
        ctx = self._setup_ctx_with_errors(csv_fixable)
        assert ctx.state["status"] == "WAITING_FOR_USER"

        # Fix the bad dept
        error_row = ctx.state["pending_fixes"][0]["row_index"]
        batch_write_fixes(ctx, row_index=error_row, fixes={"dept": "HR"})

        # Re-validate — should be clean now
        result = validate_data(ctx)
        assert result["status"] == "success"
        assert result["error_count"] == 0

        # Package
        pkg = package_results(ctx)
        assert pkg["status"] == "success"
        assert pkg["valid_count"] == 2
        assert pkg["error_count"] == 0

    def test_timeout_skip_fixes_then_package(self):
        """validate -> timeout (skip_fixes) -> package."""
        from app.tools.processing import package_results
        from app.tools.validation import skip_fixes

        ctx = self._setup_ctx_with_errors()
        assert ctx.state["status"] == "WAITING_FOR_USER"

        pending_count = len(ctx.state["pending_fixes"])
        skip_fixes(ctx)
        assert ctx.state["status"] == "RUNNING"
        assert len(ctx.state["skipped_fixes"]) == pending_count

        result = package_results(ctx)
        assert result["status"] == "success"
        assert result["error_count"] > 0

        # errors.xlsx should have _errors column
        errors_info = ctx.state["artifacts"]["errors.xlsx"]
        errors_bytes = base64.b64decode(errors_info["data"])
        df_errors = pd.read_excel(io.BytesIO(errors_bytes))
        assert "error_reason" in df_errors.columns


class TestReUploadErrorsXlsx:
    """E2E: re-upload errors.xlsx for re-validation produces clean state."""

    def test_reupload_errors_xlsx_for_revalidation(self):
        """Full round-trip: ingest → validate → skip → package → extract errors → re-ingest → clean."""
        import tempfile

        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results
        from app.tools.validation import skip_fixes, validate_data

        # --- First pass: ingest CSV with errors ---
        csv_content = MIXED_CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name

        ctx = MagicMock()
        ctx.state = {
            "dataframe_records": [],
            "dataframe_columns": [],
            "pending_fixes": [],
            "skipped_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        ingest_file(ctx, file_path=tmp_path)
        validate_data(ctx)
        assert ctx.state["status"] == "WAITING_FOR_USER"

        skip_fixes(ctx)
        assert ctx.state["status"] == "RUNNING"
        assert len(ctx.state["skipped_fixes"]) > 0

        package_result = package_results(ctx)
        assert package_result["status"] == "success"
        assert package_result["error_count"] > 0

        # --- Extract errors.xlsx as CSV for re-ingestion ---
        errors_info = ctx.state["artifacts"]["errors.xlsx"]
        errors_bytes = base64.b64decode(errors_info["data"])
        df_errors = pd.read_excel(io.BytesIO(errors_bytes))
        assert "error_reason" in df_errors.columns

        # Save errors as CSV (simulating user re-upload)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df_errors.to_csv(f, index=False)
            errors_csv_path = f.name

        # --- Second pass: re-ingest the errors file ---
        ingest_result = ingest_file(ctx, file_path=errors_csv_path)
        assert ingest_result["status"] == "success"

        # Stale validation state should be cleared
        assert ctx.state["pending_fixes"] == []
        assert ctx.state["skipped_fixes"] == []
        assert ctx.state["total_error_rows"] == 0
        assert not ctx.state["validation_complete"]
        assert ctx.state["waiting_since"] is None

        # Output columns should be stripped
        assert "error_reason" not in ctx.state["dataframe_columns"]
        assert "amount_usd" not in ctx.state["dataframe_columns"]
        assert "cost_center" not in ctx.state["dataframe_columns"]
        assert "approval_required" not in ctx.state["dataframe_columns"]
        for rec in ctx.state["dataframe_records"]:
            assert "error_reason" not in rec

        # Re-validate should work on clean data
        validate_result = validate_data(ctx)
        assert validate_result["status"] in ("success", "waiting_for_fixes")

        # Clean up
        import os

        os.unlink(tmp_path)
        os.unlink(errors_csv_path)


class TestArtifactDownload:
    """Verify artifacts are downloadable after packaging."""

    @pytest.mark.asyncio
    async def test_artifact_download_after_pipeline(self, client):
        """Upload, process (mock), then download artifacts."""
        # This test verifies the /artifacts endpoint works.
        # Since we can't run the LLM, we verify 404 for non-existent artifacts.
        async with client as c:
            resp = await c.get("/artifacts/success.xlsx")
        # No artifacts exist yet (no pipeline ran through server)
        assert resp.status_code == 404
