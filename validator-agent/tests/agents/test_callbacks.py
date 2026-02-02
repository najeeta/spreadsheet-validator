"""Tests for agent callbacks — Story 1.3."""

from unittest.mock import MagicMock, PropertyMock

from app.callbacks import after_model_modifier, before_model_modifier, on_before_agent


class TestOnBeforeAgent:
    """on_before_agent should initialize missing state keys."""

    def _make_context(self, state: dict) -> MagicMock:
        ctx = MagicMock()
        ctx.state = state
        return ctx

    def test_fills_defaults_when_empty(self):
        ctx = self._make_context({})
        on_before_agent(ctx)
        assert ctx.state["status"] == "IDLE"
        assert ctx.state["dataframe_records"] == []
        assert ctx.state["dataframe_columns"] == []
        assert ctx.state["validation_errors"] == []
        assert ctx.state["pending_fixes"] == []
        assert ctx.state["artifacts"] == {}
        assert ctx.state["validation_complete"] is False

    def test_preserves_existing_values(self):
        ctx = self._make_context({"status": "RUNNING", "file_name": "test.csv"})
        on_before_agent(ctx)
        assert ctx.state["status"] == "RUNNING"
        assert ctx.state["file_name"] == "test.csv"

    def test_uses_fresh_copies_for_mutable_defaults(self):
        ctx1 = self._make_context({})
        ctx2 = self._make_context({})
        on_before_agent(ctx1)
        on_before_agent(ctx2)
        # Mutating one should not affect the other
        ctx1.state["dataframe_records"].append({"x": 1})
        assert ctx2.state["dataframe_records"] == []


class TestBeforeModelModifier:
    """before_model_modifier should inject state summary for root agent only."""

    def _make_context(self, state: dict, agent_name: str) -> MagicMock:
        ctx = MagicMock()
        ctx.state = state
        type(ctx).agent_name = PropertyMock(return_value=agent_name)
        return ctx

    def _make_request(self, system_instruction: str = "") -> MagicMock:
        req = MagicMock()
        content = MagicMock()
        part = MagicMock()
        part.text = system_instruction
        content.parts = [part]
        req.config = MagicMock()
        req.config.system_instruction = system_instruction
        return req

    def test_injects_summary_for_root_agent(self):
        ctx = self._make_context(
            {"status": "RUNNING", "file_name": "data.csv", "dataframe_records": [{"a": 1}]},
            "SpreadsheetValidatorAgent",
        )
        req = self._make_request("You are an agent.")
        before_model_modifier(ctx, req)
        assert "status: RUNNING" in req.config.system_instruction
        assert "file_name: data.csv" in req.config.system_instruction

    def test_skips_non_root_agent(self):
        ctx = self._make_context({"status": "RUNNING"}, "IngestionAgent")
        req = self._make_request("You are ingestion.")
        before_model_modifier(ctx, req)
        assert "status:" not in req.config.system_instruction

    def test_no_a2ui_hints_in_summary(self):
        ctx = self._make_context(
            {"status": "RUNNING", "file_name": "data.csv", "dataframe_records": []},
            "SpreadsheetValidatorAgent",
        )
        req = self._make_request("You are an agent.")
        before_model_modifier(ctx, req)
        injected = req.config.system_instruction
        assert "a2ui" not in injected.lower()
        assert "render_a2ui" not in injected.lower()
        assert "activity" not in injected.lower()


class TestAfterModelModifier:
    """after_model_modifier should not modify the response."""

    def test_returns_none(self):
        ctx = MagicMock()
        resp = MagicMock()
        result = after_model_modifier(ctx, resp)
        assert result is None
