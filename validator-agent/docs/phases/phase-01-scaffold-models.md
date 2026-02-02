# Phase 1: Project Scaffold & Models

Phase 1 establishes the Python project scaffold, the shared PipelineState model, and agent lifecycle callbacks. These are the foundation that every subsequent phase depends on.

**Stories:** 1.1, 1.2, 1.3
**Quality check:** `cd validator-agent && uv sync && pytest tests/ -v`

---

## Story 1.1: Project scaffold with pyproject.toml and directory structure {#story-1.1}

### Summary

Create the validator-agent Python package scaffold with ADK dependencies, directory layout, and configuration files so that `import app` succeeds and pytest can discover tests.

### Test (write first)

**File: `tests/foundation/test_scaffold.py`**

```python
"""Tests for project scaffold — Story 1.1."""
import importlib
import pathlib


def test_app_package_importable():
    """Importing app should succeed without errors."""
    mod = importlib.import_module("app")
    assert mod is not None


def test_pyproject_toml_exists():
    """pyproject.toml must exist at the project root."""
    root = pathlib.Path(__file__).resolve().parents[2]
    assert (root / "pyproject.toml").is_file()


def test_app_agents_package_importable():
    """app.agents sub-package should be importable."""
    mod = importlib.import_module("app.agents")
    assert mod is not None


def test_app_tools_package_importable():
    """app.tools sub-package should be importable."""
    mod = importlib.import_module("app.tools")
    assert mod is not None


def test_env_example_exists():
    """.env.example must exist at the project root."""
    root = pathlib.Path(__file__).resolve().parents[2]
    assert (root / ".env.example").is_file()
```

Also create the test infrastructure files:

**File: `tests/__init__.py`** (empty)

**File: `tests/foundation/__init__.py`** (empty)

**File: `tests/conftest.py`**

```python
"""Shared pytest fixtures for all test layers."""
```

### Implementation

1. **`pyproject.toml`** at project root:

```toml
[project]
name = "spreadsheet-validator"
version = "0.1.0"
description = "Spreadsheet Validator Agent — AG-UI State-Driven React Cards"
requires-python = ">=3.11"
dependencies = [
    "google-adk>=1.15.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "ag-ui-protocol>=0.1.10",
    "ag-ui-adk>=0.4.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "httpx>=0.24.0",
    "ruff>=0.4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
```

2. **`app/__init__.py`**:

```python
"""Spreadsheet Validator Agent — AG-UI State-Driven React Cards."""
```

3. **`app/agents/__init__.py`**:

```python
"""Agent definitions."""
```

4. **`app/tools/__init__.py`**:

```python
"""Tool implementations."""
```

5. **`.env.example`**:

```
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_api_key_here
```

6. Run `uv sync` to install all dependencies.

### Success criteria

- [ ] Directory structure exists: `app/`, `app/agents/`, `app/tools/`, `tests/`
- [ ] `pyproject.toml` has all required dependencies (google-adk, fastapi, uvicorn, pandas, openpyxl, pydantic, python-dotenv, ag-ui-protocol, ag-ui-adk)
- [ ] `uv sync` succeeds without errors
- [ ] `python -c 'import app'` succeeds
- [ ] `pytest tests/foundation/ -v` passes with all tests green
- [ ] `.env.example` exists with `GOOGLE_GENAI_USE_VERTEXAI` and `GOOGLE_API_KEY`

### Quality check

```bash
cd validator-agent && uv sync && pytest tests/foundation/test_scaffold.py -v
```

### Commit message

```
feat(scaffold): initialize project with ADK dependencies

- Create pyproject.toml with google-adk, fastapi, ag-ui-adk deps
- Set up app/ package with agents/ and tools/ sub-packages
- Add tests/foundation/ scaffold verification tests
- Add .env.example and tests/conftest.py
```

---

## Story 1.2: PipelineState Pydantic model with aligned status values {#story-1.2}

### Summary

Create the shared PipelineState Pydantic model with a Status Literal covering all 10 pipeline status values. This model is used by tools to read/write session state and by the frontend to render cards. There is no `ui_events` field — Plan A uses state-driven rendering, not A2UI events.

### Test (write first)

**File: `tests/foundation/test_pipeline_state.py`**

```python
"""Tests for PipelineState model — Story 1.2."""
import pytest
from pydantic import ValidationError

from app.models import PipelineState


class TestPipelineStateDefaults:
    """PipelineState should be constructable with all defaults."""

    def test_default_construction(self):
        state = PipelineState()
        assert state is not None

    def test_default_status_is_idle(self):
        state = PipelineState()
        assert state.status == "IDLE"

    def test_default_dataframe_records_empty(self):
        state = PipelineState()
        assert state.dataframe_records == []

    def test_default_dataframe_columns_empty(self):
        state = PipelineState()
        assert state.dataframe_columns == []

    def test_default_validation_errors_empty(self):
        state = PipelineState()
        assert state.validation_errors == []

    def test_default_pending_fixes_empty(self):
        state = PipelineState()
        assert state.pending_fixes == []

    def test_default_artifacts_empty(self):
        state = PipelineState()
        assert state.artifacts == {}

    def test_default_validation_complete_false(self):
        state = PipelineState()
        assert state.validation_complete is False

    def test_default_usd_rounding_is_cents(self):
        state = PipelineState()
        assert state.usd_rounding == "cents"


class TestPipelineStateStatusValues:
    """All 10 status values should be accepted."""

    @pytest.mark.parametrize(
        "status",
        [
            "IDLE",
            "UPLOADING",
            "RUNNING",
            "VALIDATING",
            "WAITING_FOR_USER",
            "FIXING",
            "TRANSFORMING",
            "PACKAGING",
            "COMPLETED",
            "FAILED",
        ],
    )
    def test_valid_status(self, status: str):
        state = PipelineState(status=status)
        assert state.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            PipelineState(status="INVALID")

    def test_invalid_status_bogus_raises(self):
        with pytest.raises(ValidationError):
            PipelineState(status="NOT_A_STATUS")


class TestPipelineStateNoUIEvents:
    """Plan A does not use A2UI events — no ui_events field."""

    def test_no_ui_events_field(self):
        state = PipelineState()
        assert not hasattr(state, "ui_events")

    def test_ui_events_not_in_model_fields(self):
        assert "ui_events" not in PipelineState.model_fields
```

### Implementation

**File: `app/models.py`**

```python
"""Shared data models for the Spreadsheet Validator pipeline."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal[
    "IDLE",
    "UPLOADING",
    "RUNNING",
    "VALIDATING",
    "WAITING_FOR_USER",
    "FIXING",
    "TRANSFORMING",
    "PACKAGING",
    "COMPLETED",
    "FAILED",
]


class PipelineState(BaseModel):
    """Shared pipeline state stored in ADK session.

    Tools read and write this state. The frontend subscribes to state
    changes via useCoAgentStateRender to render appropriate cards.
    """

    status: Status = "IDLE"
    active_run_id: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    uploaded_file: Optional[str] = None
    dataframe_records: list[dict] = []
    dataframe_columns: list[str] = []
    validation_errors: list[dict] = []
    validation_complete: bool = False
    pending_fixes: list[dict] = []
    artifacts: dict[str, str] = {}
    as_of: Optional[str] = None
    usd_rounding: Optional[Literal["cents", "whole"]] = "cents"
    cost_center_map: dict[str, str] = {}
```

### Success criteria

- [ ] `PipelineState()` returns a valid instance with all defaults
- [ ] `status` default is `"IDLE"`
- [ ] All 10 status values are valid (parametrized test)
- [ ] `PipelineState(status="INVALID")` raises `ValidationError`
- [ ] `dataframe_records` defaults to `[]`
- [ ] `usd_rounding` defaults to `"cents"`
- [ ] No `ui_events` field exists on the model
- [ ] All tests in `tests/foundation/test_pipeline_state.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/foundation/test_pipeline_state.py -v
```

### Commit message

```
feat(models): add PipelineState with aligned status values

- 10-value Status Literal matching frontend PipelineStatus
- All fields with sensible defaults for session initialization
- No ui_events field — Plan A uses state-driven rendering
```

---

## Story 1.3: Agent callbacks: state initialization and prompt injection {#story-1.3}

### Summary

Create callback functions that initialize session state with PipelineState defaults and inject a state summary into the root agent's system prompt. No A2UI hints are injected anywhere.

### Test (write first)

**File: `tests/agents/test_callbacks.py`**

```python
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
```

Also create:

**File: `tests/agents/__init__.py`** (empty)

### Implementation

**File: `app/callbacks.py`**

```python
"""ADK lifecycle callbacks for state initialization and prompt injection."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default values for PipelineState keys in session state.
# Mutable defaults are wrapped in lambdas to produce fresh copies.
_STATE_DEFAULTS: dict[str, Any] = {
    "status": "IDLE",
    "active_run_id": None,
    "file_path": None,
    "file_name": None,
    "uploaded_file": None,
    "dataframe_records": lambda: [],
    "dataframe_columns": lambda: [],
    "validation_errors": lambda: [],
    "validation_complete": False,
    "pending_fixes": lambda: [],
    "artifacts": lambda: {},
    "as_of": None,
    "usd_rounding": "cents",
    "cost_center_map": lambda: {},
}

_ROOT_AGENT_NAME = "SpreadsheetValidatorAgent"


def on_before_agent(callback_context: Any) -> None:
    """Idempotent state initialization — fill missing keys with defaults."""
    state = callback_context.state
    initialized = []
    for key, default in _STATE_DEFAULTS.items():
        if key not in state:
            value = default() if callable(default) else default
            state[key] = value
            initialized.append(key)
    if initialized:
        logger.debug("Initialized state keys: %s", initialized)


def before_model_modifier(callback_context: Any, llm_request: Any) -> None:
    """Inject a state summary into the root agent's system instruction."""
    if callback_context.agent_name != _ROOT_AGENT_NAME:
        return

    state = callback_context.state
    lines = [
        "\n--- Current Pipeline State ---",
        f"status: {state.get('status', 'IDLE')}",
    ]
    if state.get("file_name"):
        lines.append(f"file_name: {state['file_name']}")
    records = state.get("dataframe_records", [])
    if records:
        lines.append(f"row_count: {len(records)}")
    columns = state.get("dataframe_columns", [])
    if columns:
        lines.append(f"columns: {columns}")
    errors = state.get("validation_errors", [])
    if errors:
        lines.append(f"error_count: {len(errors)}")
    fixes = state.get("pending_fixes", [])
    if fixes:
        lines.append(f"pending_fixes: {len(fixes)}")
    artifacts = state.get("artifacts", {})
    if artifacts:
        lines.append(f"artifacts: {list(artifacts.keys())}")
    if state.get("as_of"):
        lines.append(f"as_of: {state['as_of']}")
    if state.get("usd_rounding"):
        lines.append(f"usd_rounding: {state['usd_rounding']}")
    lines.append("--- End Pipeline State ---\n")

    summary = "\n".join(lines)
    existing = llm_request.config.system_instruction or ""
    llm_request.config.system_instruction = existing + summary


def after_model_modifier(callback_context: Any, llm_response: Any) -> None:
    """Log response for debugging. Does not modify the response."""
    logger.debug("after_model_modifier called — no modifications applied")
    return None
```

### Success criteria

- [ ] `on_before_agent` initializes all state fields when state is empty
- [ ] `on_before_agent` does NOT overwrite existing state values
- [ ] `on_before_agent` uses fresh list/dict copies for mutable defaults
- [ ] `before_model_modifier` only modifies prompts for `SpreadsheetValidatorAgent`
- [ ] `before_model_modifier` injects state summary into system instruction
- [ ] State summary includes status, file_name, row count when data is loaded
- [ ] No A2UI hint is generated or injected
- [ ] `after_model_modifier` returns `None` (no modification)
- [ ] All tests in `tests/agents/test_callbacks.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/agents/test_callbacks.py -v
```

### Commit message

```
feat(callbacks): add state init and prompt injection callbacks

- on_before_agent fills missing state keys with PipelineState defaults
- before_model_modifier injects state summary for root agent only
- after_model_modifier is a no-op for debugging
- No A2UI hints injected anywhere
```
