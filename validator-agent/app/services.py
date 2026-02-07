"""Shared services for the application.

Switches between InMemory (development) and VertexAi/GCS (production)
based on the ENVIRONMENT env var.
"""

import os

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

if ENVIRONMENT == "production":
    from google.adk.artifacts import GcsArtifactService
    from google.adk.sessions import VertexAiSessionService

    _project = os.environ["GOOGLE_CLOUD_PROJECT"]
    _location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    _agent_engine_id = os.environ["AGENT_ENGINE_ID"]
    _bucket = os.environ["GCS_ARTIFACT_BUCKET"]

    session_service = VertexAiSessionService(
        project=_project,
        location=_location,
        agent_engine_id=_agent_engine_id,
    )
    artifact_service = GcsArtifactService(bucket_name=_bucket)
else:
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.sessions import InMemorySessionService

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
