"""Tests for FastAPI server — Story 4.1."""

import io
import pathlib

import pytest
import httpx

from app.server import fastapi_app


@pytest.fixture
def client():
    """Create an async test client for the FastAPI app."""
    transport = httpx.ASGITransport(app=fastapi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestHealthEndpoint:
    """GET /health returns status healthy."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        async with client as c:
            resp = await c.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestRunEndpoint:
    """POST /run creates a session."""

    @pytest.mark.asyncio
    async def test_create_run(self, client):
        async with client as c:
            resp = await c.post("/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_create_run_returns_session_id(self, client):
        async with client as c:
            resp = await c.post("/run")
        data = resp.json()
        # Session ID should be a non-empty string (UUID)
        assert isinstance(data.get("session_id"), str)
        assert len(data["session_id"]) > 0


class TestUploadEndpoint:
    """POST /upload saves file as artifact (no state updates)."""

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        async with client as c:
            # First create a session
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]

            # Upload a CSV using form data
            csv_content = b"employee_id,dept,amount\nEMP001,Engineering,1500"
            files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
            resp = await c.post(
                "/upload",
                data={"session_id": session_id},
                files=files,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["file_name"] == "test.csv"

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_type(self, client):
        async with client as c:
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]

            files = {"file": ("test.json", io.BytesIO(b'{"a": 1}'), "application/json")}
            resp = await c.post(
                "/upload",
                data={"session_id": session_id},
                files=files,
            )

        assert resp.status_code == 400


class TestRunsEndpoint:
    """GET /runs lists sessions; GET /runs/{id} returns full state."""

    @pytest.mark.asyncio
    async def test_list_runs(self, client):
        async with client as c:
            await c.post("/run")
            resp = await c.get("/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_run_detail(self, client):
        async with client as c:
            run_resp = await c.post("/run")
            session_id = run_resp.json()["session_id"]
            resp = await c.get(f"/runs/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        # Session state has AG-UI metadata, status is set by /run
        assert "_ag_ui_thread_id" in data

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, client):
        async with client as c:
            resp = await c.get("/runs/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs_strips_heavy_keys(self, client):
        async with client as c:
            await c.post("/run")
            resp = await c.get("/runs")
        data = resp.json()
        if data:
            run = data[0]
            # Heavy keys should be stripped from listing
            assert "dataframe_records" not in run


class TestArtifactsEndpoint:
    """GET /artifacts/{name} returns artifact or 404."""

    @pytest.mark.asyncio
    async def test_artifact_not_found(self, client):
        async with client as c:
            resp = await c.get("/artifacts/nonexistent.xlsx")
        assert resp.status_code == 404


class TestFeedbackEndpoint:
    """POST /feedback records feedback."""

    @pytest.mark.asyncio
    async def test_feedback_returns_201(self, client):
        async with client as c:
            resp = await c.post(
                "/feedback",
                json={"session_id": "test", "rating": "thumbs_up", "comment": "Good"},
            )
        assert resp.status_code == 201


class TestNoMonkeyPatches:
    """server.py must not import monkey-patch modules."""

    def test_no_monkey_patch_imports(self):
        source = pathlib.Path(__file__).resolve().parents[2] / "app" / "server.py"
        content = source.read_text()
        assert "monkey_patch" not in content.lower()
        assert "render_a2ui" not in content


class TestAgentEndpointExists:
    """/agent endpoint should be registered."""

    @pytest.mark.asyncio
    async def test_agent_endpoint_registered(self, client):
        async with client as c:
            # AG-UI endpoint should exist — a GET may return 405 (method not allowed)
            # or the endpoint may require SSE headers. We just check it's routed.
            resp = await c.post(
                "/agent",
                headers={"Content-Type": "application/json"},
                content="{}",
            )
        # Should not be 404 — endpoint exists
        assert resp.status_code != 404
