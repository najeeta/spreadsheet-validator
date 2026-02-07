"""Tests for app/services.py — environment-aware service construction."""

from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService

from app.services import ENVIRONMENT, artifact_service, session_service


class TestDevelopmentServices:
    """In development mode, services should be InMemory variants."""

    def test_environment_is_development(self):
        # Default (no ENVIRONMENT env var) should be development
        assert ENVIRONMENT == "development"

    def test_session_service_is_in_memory(self):
        assert isinstance(session_service, InMemorySessionService)

    def test_artifact_service_is_in_memory(self):
        assert isinstance(artifact_service, InMemoryArtifactService)
