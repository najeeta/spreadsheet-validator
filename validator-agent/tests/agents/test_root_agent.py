"""Tests for root agent — Story 3.2."""

from google.adk.tools import AgentTool

from app.agents.root_agent import root_agent


class TestRootAgentConfig:
    """Root agent has AgentTool wrappers + write_fix."""

    def test_name(self):
        assert root_agent.name == "SpreadsheetValidatorAgent"

    def test_has_no_sub_agents(self):
        # All agents are now AgentTools, not sub_agents
        sub_agents = getattr(root_agent, "sub_agents", [])
        assert len(sub_agents) == 0

    def test_has_seven_tools(self):
        # 3 AgentTools + write_fix + batch_write_fixes + skip_row + skip_fixes
        assert len(root_agent.tools) == 7

    def test_has_agent_tools(self):
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        assert len(agent_tools) == 3

    def test_agent_tool_names(self):
        agent_tools = [t for t in root_agent.tools if isinstance(t, AgentTool)]
        names = {t.agent.name for t in agent_tools}
        assert "load_spreadsheet" in names
        assert "validate_data" in names
        assert "process_results" in names

    def test_has_write_fix_tool(self):
        non_agent_tools = [t for t in root_agent.tools if not isinstance(t, AgentTool)]
        tool_names = {t.__name__ if callable(t) else t.name for t in non_agent_tools}
        assert "write_fix" in tool_names

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
