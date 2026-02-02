"""Tests for root agent — Story 3.2."""

from app.agents.root_agent import root_agent


class TestRootAgentConfig:
    """Root agent has correct name, sub-agents, and no tools."""

    def test_name(self):
        assert root_agent.name == "SpreadsheetValidatorAgent"

    def test_has_three_sub_agents(self):
        assert len(root_agent.sub_agents) == 3

    def test_sub_agent_names(self):
        names = {a.name for a in root_agent.sub_agents}
        assert "IngestionAgent" in names
        assert "ValidationAgent" in names
        assert "ProcessingAgent" in names

    def test_no_tools(self):
        # Root agent delegates everything to sub-agents
        tools = getattr(root_agent, "tools", None)
        assert tools is None or len(tools) == 0

    def test_has_model(self):
        assert root_agent.model is not None


class TestRootAgentCallbacks:
    """Root agent has lifecycle callbacks registered."""

    def test_before_agent_callback(self):
        assert root_agent.before_agent_callback is not None

    def test_before_model_callback(self):
        assert root_agent.before_model_callback is not None

    def test_after_model_callback(self):
        assert root_agent.after_model_callback is not None


class TestRootAgentInstruction:
    """Root agent instruction contains workflow rules."""

    def test_instruction_mentions_ingestion(self):
        assert "Ingestion" in root_agent.instruction or "ingest" in root_agent.instruction.lower()

    def test_instruction_mentions_validation(self):
        assert "Validation" in root_agent.instruction or "validat" in root_agent.instruction.lower()

    def test_instruction_mentions_processing(self):
        assert "Processing" in root_agent.instruction or "process" in root_agent.instruction.lower()


class TestAppWrapper:
    """App wraps root_agent with correct name."""

    def test_app_importable(self):
        from app.agent import adk_app

        assert adk_app is not None

    def test_app_name(self):
        from app.agent import adk_app

        assert adk_app.name == "spreadsheet_validator"


class TestModuleExport:
    """app/__init__.py exports root_agent."""

    def test_root_agent_exported(self):
        from app import root_agent as exported

        assert exported is not None
        assert exported.name == "SpreadsheetValidatorAgent"
