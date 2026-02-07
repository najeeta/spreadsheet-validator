"""Integration tests for async pipeline endpoints — POST /runs and POST /runs/{run_id}/answers."""

import io

import pytest
import httpx

from app.server import fastapi_app
from app.run_manager import run_manager


@pytest.fixture
def client():
    """Create an async test client for the FastAPI app."""
    transport = httpx.ASGITransport(app=fastapi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture(autouse=True)
def _clean_run_manager():
    """Clean up run_manager between tests."""
    yield
    # Clear all runs after each test
    run_manager._runs.clear()


class TestPostRuns:
    """POST /runs — async run creation."""

    @pytest.mark.asyncio
    async def test_returns_202_with_run_id(self, client):
        csv_content = b"employee_id,dept,amount,currency,spend_date,vendor,fx_rate\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        async with client as c:
            resp = await c.post("/runs", files=files)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_run_id_is_string(self, client):
        csv_content = b"employee_id,dept,amount\nEMP001,ENG,1500"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        async with client as c:
            resp = await c.post("/runs", files=files)
        data = resp.json()
        assert isinstance(data["run_id"], str)
        assert len(data["run_id"]) > 0

    @pytest.mark.asyncio
    async def test_rejects_bad_file_type(self, client):
        files = {"file": ("test.json", io.BytesIO(b'{"a": 1}'), "application/json")}
        async with client as c:
            resp = await c.post("/runs", files=files)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_txt_file(self, client):
        files = {"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")}
        async with client as c:
            resp = await c.post("/runs", files=files)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_accepts_xlsx(self, client):
        """XLSX extension is accepted (content doesn't need to be valid for the endpoint check)."""
        # Create minimal xlsx-like content; the endpoint validates extension, not content
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["employee_id", "dept", "amount", "currency", "spend_date", "vendor", "fx_rate"])
        ws.append(["EMP001", "ENG", 1500, "USD", "2024-01-15", "Acme", 1.0])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        files = {
            "file": (
                "test.xlsx",
                buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        async with client as c:
            resp = await c.post("/runs", files=files)
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_run_visible_via_get_runs(self, client):
        """After POST /runs, the run should appear in GET /runs/{id}."""
        csv_content = b"employee_id,dept,amount,currency,spend_date,vendor,fx_rate\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        async with client as c:
            resp = await c.post("/runs", files=files)
            run_id = resp.json()["run_id"]
            detail = await c.get(f"/runs/{run_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["file_name"] == "test.csv"


class TestPostAnswersValidation:
    """POST /runs/{run_id}/answers — error cases."""

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        async with client as c:
            resp = await c.post(
                "/runs/nonexistent-id/answers",
                json={"skip_all": True},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_conflict_when_not_waiting(self, client):
        """POST /answers on a run that isn't WAITING_FOR_USER returns 409."""
        csv_content = b"employee_id,dept,amount,currency,spend_date,vendor,fx_rate\nEMP001,ENG,1500,USD,2024-01-15,Acme,1.0"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        async with client as c:
            resp = await c.post("/runs", files=files)
            run_id = resp.json()["run_id"]

            # The run was just created with status RUNNING, not WAITING_FOR_USER
            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={"skip_all": True},
            )
        assert resp.status_code == 409


class TestPostAnswersWithState:
    """POST /runs/{run_id}/answers — applying fixes to WAITING_FOR_USER sessions."""

    async def _create_waiting_run(self, client):
        """Create a session in WAITING_FOR_USER state with a registered RunContext.

        Does NOT use POST /runs to avoid background task interference.
        Sets up the session and run_manager directly.
        """
        import uuid

        from app.server import APP_NAME, USER_ID
        from app.services import session_service

        run_id = str(uuid.uuid4())

        # Create session directly with WAITING_FOR_USER state
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=run_id,
            state={
                "status": "WAITING_FOR_USER",
                "file_name": "test.csv",
                "_ag_ui_thread_id": run_id,
                "_ag_ui_app_name": APP_NAME,
                "_ag_ui_user_id": USER_ID,
                "dataframe_records": [
                    {
                        "employee_id": "EMP001",
                        "dept": "BAD",
                        "amount": 1500,
                        "currency": "USD",
                        "spend_date": "2024-01-15",
                        "vendor": "Acme",
                        "fx_rate": 1.0,
                    }
                ],
                "pending_review": [
                    {
                        "row_index": 0,
                        "field": "dept",
                        "current_value": "BAD",
                        "error_message": "Invalid department",
                    },
                ],
                "skipped_rows": [],
                "all_errors": [
                    {
                        "row_index": 0,
                        "field": "dept",
                        "current_value": "BAD",
                        "error_message": "Invalid department",
                    }
                ],
            },
        )

        # Register in run_manager so the endpoint can find it
        run_manager.create_run(run_id)

        return run_id

    @pytest.mark.asyncio
    async def test_apply_single_fix(self, client):
        async with client as c:
            run_id = await self._create_waiting_run(c)

            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={
                    "fixes": [{"row_index": 0, "field": "dept", "new_value": "ENG"}],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied_count"] == 1
        assert data["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_apply_row_fixes(self, client):
        async with client as c:
            run_id = await self._create_waiting_run(c)

            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={
                    "row_fixes": [{"row_index": 0, "fixes": {"dept": "ENG"}}],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied_count"] == 1

    @pytest.mark.asyncio
    async def test_skip_all(self, client):
        async with client as c:
            run_id = await self._create_waiting_run(c)

            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={"skip_all": True},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_count"] == 1
        assert data["pending_review_count"] == 0

    @pytest.mark.asyncio
    async def test_skip_specific_row(self, client):
        async with client as c:
            run_id = await self._create_waiting_run(c)

            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={"skip_rows": [0]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skipped_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_body_is_noop(self, client):
        async with client as c:
            run_id = await self._create_waiting_run(c)

            resp = await c.post(
                f"/runs/{run_id}/answers",
                json={},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied_count"] == 0
        assert data["skipped_count"] == 0
        # Pending fixes still remain since nothing was done
        assert data["pending_review_count"] == 1
