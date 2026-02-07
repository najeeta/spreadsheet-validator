"""Tests for sub-agents — Story 3.1."""

from app.agents.ingestion import ingestion_agent
from app.agents.processing import processing_agent
from app.agents.validation import validation_agent


class TestIngestionAgent:
    """IngestionAgent has 4 tools and correct config."""

    def test_name(self):
        assert ingestion_agent.name == "load_spreadsheet"

    def test_tool_count(self):
        assert len(ingestion_agent.tools) == 4

    def test_tool_names(self):
        tool_names = {t.__name__ if callable(t) else t.name for t in ingestion_agent.tools}
        assert "request_file_upload" in tool_names
        assert "ingest_uploaded_file" in tool_names
        assert "confirm_ingestion" in tool_names
        assert "ingest_file" in tool_names

    def test_no_render_a2ui(self):
        tool_names = {
            (t.__name__ if callable(t) else getattr(t, "name", str(t)))
            for t in ingestion_agent.tools
        }
        assert "render_a2ui" not in tool_names

    def test_has_model(self):
        assert ingestion_agent.model is not None

    def test_has_output_key(self):
        assert ingestion_agent.output_key is not None

    def test_has_input_schema(self):
        assert ingestion_agent.input_schema is not None


class TestValidationAgent:
    """ValidationAgent has 1 tool (validate_data) — HITL handled by root."""

    def test_name(self):
        assert validation_agent.name == "validate_data"

    def test_tool_count(self):
        assert len(validation_agent.tools) == 1

    def test_tool_names(self):
        tool_names = {t.__name__ if callable(t) else t.name for t in validation_agent.tools}
        assert "validate_data" in tool_names

    def test_no_render_a2ui(self):
        tool_names = {
            (t.__name__ if callable(t) else getattr(t, "name", str(t)))
            for t in validation_agent.tools
        }
        assert "render_a2ui" not in tool_names

    def test_has_model(self):
        assert validation_agent.model is not None

    def test_has_output_key(self):
        assert validation_agent.output_key is not None

    def test_has_no_input_schema(self):
        assert validation_agent.input_schema is None


class TestProcessingAgent:
    """ProcessingAgent has 2 tools and correct config."""

    def test_name(self):
        assert processing_agent.name == "process_results"

    def test_tool_count(self):
        assert len(processing_agent.tools) == 2

    def test_tool_names(self):
        tool_names = {t.__name__ if callable(t) else t.name for t in processing_agent.tools}
        assert "transform_data" in tool_names
        assert "package_results" in tool_names

    def test_no_render_a2ui(self):
        tool_names = {
            (t.__name__ if callable(t) else getattr(t, "name", str(t)))
            for t in processing_agent.tools
        }
        assert "render_a2ui" not in tool_names

    def test_has_model(self):
        assert processing_agent.model is not None

    def test_has_output_key(self):
        assert processing_agent.output_key is not None

    def test_has_no_input_schema(self):
        assert processing_agent.input_schema is None


class TestAgentsExport:
    """All agents should be importable from app.agents."""

    def test_import_from_agents_package(self):
        from app.agents import ingestion_agent, processing_agent, validation_agent

        assert ingestion_agent is not None
        assert validation_agent is not None
        assert processing_agent is not None
