"""End-to-end integration test: full pipeline — Story 6.1."""

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
MIXED_CSV = """employee_id,dept,amount,currency,spend_date,vendor,fx_rate
EMP001,Engineering,1500.00,USD,2024-01-15,Acme Corp,1.0
EMP002,Marketing,2500.50,EUR,2024-02-20,Beta Inc,1.08
INVALID,BadDept,-100,XYZ,01/15/2024,,0.01
EMP003,Sales,750.00,GBP,2024-03-10,Gamma Ltd,1.27
"""


class TestFullPipeline:
    """Full pipeline: session -> upload -> ingest -> validate -> transform -> package."""

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """Step 1: Create a session via POST /run."""
        async with client as c:
            resp = await c.post("/run", params={"thread_id": "e2e-test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        """Step 2: Upload a CSV via POST /upload."""
        async with client as c:
            await c.post("/run", params={"thread_id": "e2e-upload"})
            files = {"file": ("mixed.csv", io.BytesIO(MIXED_CSV.encode()), "text/csv")}
            resp = await c.post("/upload", params={"thread_id": "e2e-upload"}, files=files)
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_session_has_uploaded_file(self, client):
        """Step 3: Verify session state has uploaded_file set."""
        async with client as c:
            run_resp = await c.post("/run", params={"thread_id": "e2e-state"})
            session_id = run_resp.json()["session_id"]

            files = {"file": ("test.csv", io.BytesIO(MIXED_CSV.encode()), "text/csv")}
            await c.post("/upload", params={"thread_id": "e2e-state"}, files=files)

            detail_resp = await c.get(f"/runs/{session_id}")
        data = detail_resp.json()
        assert data.get("uploaded_file") == "test.csv"


class TestToolChainDirect:
    """Test tool chain directly (no LLM) to verify data flow."""

    @pytest.mark.asyncio
    async def test_full_tool_chain(self):
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
            "validation_errors": [],
            "validation_complete": False,
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
        assert ctx.state["validation_complete"] is True
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

        # Step 4: Package — save artifacts
        saved_artifacts = {}

        async def mock_save(filename, artifact):
            saved_artifacts[filename] = artifact

        ctx.save_artifact = mock_save

        package_result = await package_results(ctx)
        assert package_result["status"] == "success"
        assert ctx.state["status"] == "COMPLETED"
        assert "success.xlsx" in ctx.state["artifacts"]
        assert "errors.xlsx" in ctx.state["artifacts"]

        # Verify success.xlsx is valid Excel
        success_bytes = saved_artifacts["success.xlsx"].inline_data.data
        df_success = pd.read_excel(io.BytesIO(success_bytes))
        assert len(df_success) > 0
        assert "amount_usd" in df_success.columns

    @pytest.mark.asyncio
    async def test_tool_chain_with_errors(self):
        """Tool chain with invalid data produces errors in package."""
        from unittest.mock import MagicMock

        from app.tools.ingestion import ingest_file
        from app.tools.processing import package_results
        from app.tools.validation import validate_data

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
            "validation_errors": [],
            "validation_complete": False,
            "pending_fixes": [],
            "artifacts": {},
            "status": "IDLE",
        }

        # Ingest
        ingest_result = ingest_file(ctx, file_path=tmp_path)
        assert ingest_result["status"] == "success"
        assert ingest_result["row_count"] == 4

        # Validate — should find errors in the INVALID row
        validate_result = validate_data(ctx)
        assert validate_result["error_count"] > 0
        assert ctx.state["validation_complete"] is True

        # Package — should separate valid and invalid
        saved = {}

        async def mock_save(filename, artifact):
            saved[filename] = artifact

        ctx.save_artifact = mock_save
        package_result = await package_results(ctx)

        assert package_result["valid_count"] > 0
        assert package_result["error_count"] > 0
        assert ctx.state["status"] == "COMPLETED"

        # Verify errors.xlsx has _errors column
        errors_bytes = saved["errors.xlsx"].inline_data.data
        df_errors = pd.read_excel(io.BytesIO(errors_bytes))
        assert "_errors" in df_errors.columns
        assert len(df_errors) > 0

        # Clean up
        import os

        os.unlink(tmp_path)


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
