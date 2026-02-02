# Phase 3: Agent Core

Phase 3 defines the three sub-agents (Ingestion, Validation, Processing) with their tool assignments and the root orchestrator agent with callbacks, workflow rules, and ADK App wrapper. No agent uses a `render_a2ui` tool — Plan A drives the frontend purely through state changes.

**Stories:** 3.1, 3.2
**Depends on:** Phase 1 (callbacks), Phase 2 (all tools)
**Quality check:** `cd validator-agent && pytest tests/agents/ -v`

---

## Story 3.1: Sub-agents — IngestionAgent, ValidationAgent, ProcessingAgent {#story-3.1}

### Summary

Create the three LlmAgent sub-agents with clear instruction text, proper tool assignments, and output keys. Each agent is a specialist that owns a portion of the pipeline. No agent carries a `render_a2ui` tool — all UI is state-driven.

### Test (write first)

**File: `tests/agents/test_sub_agents.py`**

```python
"""Tests for sub-agents — Story 3.1."""
from app.agents.ingestion import ingestion_agent
from app.agents.processing import processing_agent
from app.agents.validation import validation_agent


class TestIngestionAgent:
    """IngestionAgent has 3 tools and correct config."""

    def test_name(self):
        assert ingestion_agent.name == "IngestionAgent"

    def test_tool_count(self):
        assert len(ingestion_agent.tools) == 3

    def test_tool_names(self):
        tool_names = {t.__name__ if callable(t) else t.name for t in ingestion_agent.tools}
        assert "request_file_upload" in tool_names
        assert "ingest_file" in tool_names
        assert "ingest_uploaded_file" in tool_names

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


class TestValidationAgent:
    """ValidationAgent has 3 tools and correct config."""

    def test_name(self):
        assert validation_agent.name == "ValidationAgent"

    def test_tool_count(self):
        assert len(validation_agent.tools) == 3

    def test_tool_names(self):
        tool_names = {t.__name__ if callable(t) else t.name for t in validation_agent.tools}
        assert "validate_data" in tool_names
        assert "request_user_fix" in tool_names
        assert "write_fix" in tool_names

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


class TestProcessingAgent:
    """ProcessingAgent has 2 tools and correct config."""

    def test_name(self):
        assert processing_agent.name == "ProcessingAgent"

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


class TestAgentsExport:
    """All agents should be importable from app.agents."""

    def test_import_from_agents_package(self):
        from app.agents import ingestion_agent, processing_agent, validation_agent

        assert ingestion_agent is not None
        assert validation_agent is not None
        assert processing_agent is not None
```

### Implementation

**File: `app/agents/ingestion.py`**

```python
"""IngestionAgent — handles file upload signaling and CSV/XLSX parsing."""
from google.adk import LlmAgent

from app.tools.ingestion import ingest_file, ingest_uploaded_file, request_file_upload

ingestion_agent = LlmAgent(
    name="IngestionAgent",
    model="gemini-2.0-flash",
    instruction="""You are the Ingestion Agent. Your job is to help users upload and ingest
spreadsheet files for validation.

Workflow:
1. If the user has not uploaded a file, call request_file_upload to prompt them.
2. If state['uploaded_file'] is set, call ingest_uploaded_file to parse the artifact.
3. If given a file path directly, call ingest_file with the path.

After successful ingestion, report the row count and column names to the user.
Then transfer control back to the root agent for the next pipeline step.""",
    tools=[request_file_upload, ingest_file, ingest_uploaded_file],
    output_key="ingestion_result",
)
```

**File: `app/agents/validation.py`**

```python
"""ValidationAgent — enforces 7 business rules and manages fix lifecycle."""
from google.adk import LlmAgent

from app.tools.validation import request_user_fix, validate_data, write_fix

validation_agent = LlmAgent(
    name="ValidationAgent",
    model="gemini-2.0-flash",
    instruction="""You are the Validation Agent. Your job is to validate spreadsheet data
against business rules and help users fix errors.

Workflow:
1. Call validate_data to check all records against 7 business rules.
2. If there are no errors, report success and transfer to the root agent.
3. If there are errors, present them to the user and use request_user_fix
   for each error that needs user input.
4. When the user provides a fix, call write_fix to apply it.
5. After all fixes are applied, call validate_data again to re-check.
6. Repeat until all data is valid, then transfer to the root agent.

Business rules checked:
- employee_id: Must match EMP followed by 3+ digits, must be unique
- dept: Must be a valid department (Engineering, Marketing, Sales, etc.)
- amount: Must be > 0 and <= 100,000
- currency: Must be a valid ISO 4217 code
- spend_date: Must be YYYY-MM-DD format and not in the future
- vendor: Must not be empty
- fx_rate: Required for non-USD currencies, must be in [0.1, 500]""",
    tools=[validate_data, request_user_fix, write_fix],
    output_key="validation_result",
)
```

**File: `app/agents/processing.py`**

```python
"""ProcessingAgent — transforms data and packages results into Excel artifacts."""
from google.adk import LlmAgent

from app.tools.processing import package_results, transform_data

processing_agent = LlmAgent(
    name="ProcessingAgent",
    model="gemini-2.0-flash",
    instruction="""You are the Processing Agent. Your job is to transform validated data
and package results into downloadable Excel files.

Workflow:
1. If the root agent requests transformations, call transform_data to add
   computed columns (e.g., amount_usd = amount * fx_rate).
2. Call package_results to create success.xlsx (valid rows) and
   errors.xlsx (invalid rows with error details).
3. Report the artifact names and summary statistics to the user.
4. Transfer control back to the root agent.""",
    tools=[transform_data, package_results],
    output_key="processing_result",
)
```

**Update `app/agents/__init__.py`:**

```python
"""Agent definitions."""
from app.agents.ingestion import ingestion_agent
from app.agents.processing import processing_agent
from app.agents.validation import validation_agent

__all__ = ["ingestion_agent", "validation_agent", "processing_agent"]
```

### Success criteria

- [ ] `IngestionAgent` has 3 tools: `request_file_upload`, `ingest_file`, `ingest_uploaded_file`
- [ ] `ValidationAgent` has 3 tools: `validate_data`, `request_user_fix`, `write_fix`
- [ ] `ProcessingAgent` has 2 tools: `transform_data`, `package_results`
- [ ] No agent has `render_a2ui` in its tools list
- [ ] Each agent has `model='gemini-2.0-flash'`
- [ ] Each agent has an `output_key` set
- [ ] Each agent's instruction describes its workflow clearly
- [ ] All three agents export from `app/agents/__init__.py`
- [ ] All tests in `tests/agents/test_sub_agents.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/agents/test_sub_agents.py -v
```

### Commit message

```
feat(agents): add ingestion, validation, processing sub-agents

- IngestionAgent with 3 file handling tools
- ValidationAgent with 3 validation and fix tools
- ProcessingAgent with 2 transform and packaging tools
- No render_a2ui tool on any agent
```

---

## Story 3.2: Root agent — SpreadsheetValidatorAgent orchestrator {#story-3.2}

### Summary

Create the root orchestrator agent that coordinates the three sub-agents with workflow transfer rules, registers lifecycle callbacks, and wraps everything in an ADK App. The root agent has no tools of its own (no `render_a2ui`). It delegates all work to sub-agents.

### Test (write first)

**File: `tests/agents/test_root_agent.py`**

```python
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
```

### Implementation

**File: `app/agents/root_agent.py`**

```python
"""Root orchestrator agent — SpreadsheetValidatorAgent."""
from google.adk import Agent

from app.agents.ingestion import ingestion_agent
from app.agents.processing import processing_agent
from app.agents.validation import validation_agent
from app.callbacks import after_model_modifier, before_model_modifier, on_before_agent

root_agent = Agent(
    name="SpreadsheetValidatorAgent",
    model="gemini-2.0-flash",
    instruction="""You are the Spreadsheet Validator Agent, an orchestrator that manages
a data validation pipeline. You coordinate three specialist sub-agents:

1. **IngestionAgent** — Handles file upload and CSV/XLSX parsing.
2. **ValidationAgent** — Validates data against 7 business rules and manages fixes.
3. **ProcessingAgent** — Transforms data and packages results into Excel files.

## Workflow Rules

1. When a user provides a file (upload or path), transfer to IngestionAgent.
2. After ingestion completes successfully, IMMEDIATELY transfer to ValidationAgent.
3. After validation:
   - If NO errors: Transfer to ProcessingAgent.
   - If errors exist: ValidationAgent will interact with the user to fix them.
4. After all fixes are applied and re-validation passes, transfer to ProcessingAgent.
5. After processing completes, report the final summary to the user:
   - Total rows processed
   - Valid vs invalid count
   - Available artifact downloads (success.xlsx, errors.xlsx)

## Important
- Do NOT attempt to validate or process data yourself — always delegate to sub-agents.
- Keep the user informed of progress at each step.
- If any step fails, report the error clearly and suggest next steps.""",
    sub_agents=[ingestion_agent, validation_agent, processing_agent],
    before_agent_callback=on_before_agent,
    before_model_callback=before_model_modifier,
    after_model_callback=after_model_modifier,
)
```

**File: `app/agent.py`**

```python
"""ADK App wrapper for the SpreadsheetValidator agent."""
from google.adk import App

from app.agents.root_agent import root_agent

adk_app = App(
    name="spreadsheet_validator",
    root_agent=root_agent,
)
```

**Update `app/__init__.py`:**

```python
"""Spreadsheet Validator Agent — AG-UI State-Driven React Cards."""
from app.agents.root_agent import root_agent

__all__ = ["root_agent"]
```

### Success criteria

- [ ] Root agent has `name='SpreadsheetValidatorAgent'`
- [ ] Root agent has 3 sub-agents (Ingestion, Validation, Processing)
- [ ] Root agent has no tools (empty or omitted tools list)
- [ ] Root agent has `before_agent_callback` set
- [ ] Root agent has `before_model_callback` set
- [ ] Root agent has `after_model_callback` set
- [ ] App wraps root_agent with `name='spreadsheet_validator'`
- [ ] `app/__init__.py` exports `root_agent`
- [ ] Instruction contains workflow rules for agent transfers
- [ ] All tests in `tests/agents/test_root_agent.py` pass

### Quality check

```bash
cd validator-agent && pytest tests/agents/test_root_agent.py -v
```

### Commit message

```
feat(agents): add root orchestrator agent

- SpreadsheetValidatorAgent with 3 sub-agents and workflow rules
- Lifecycle callbacks: state init, prompt injection, response logging
- ADK App wrapper with name='spreadsheet_validator'
- app/__init__.py exports root_agent for ADK discovery
```
