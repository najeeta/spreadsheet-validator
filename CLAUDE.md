# SpreadsheetValidator — AG-UI State-Driven React Cards

## Overview

The **SpreadsheetValidator** uses AG-UI state-driven rendering to build a validation pipeline with Google ADK agents, served via ag-ui-adk FastAPI SSE, with a Next.js CopilotKit frontend. The frontend uses `useCoAgentStateRender` to render custom React cards based on agent state changes — no A2UI protocol, no monkey-patches, no `render_a2ui` tool. The agent writes to `state["ui"]` and the frontend renders cards accordingly.

## Quick Reference

```bash
# Backend — install dependencies
cd validator-agent && uv sync

# Backend — run tests
cd validator-agent && pytest tests/ -v

# Backend — run tests with coverage
cd validator-agent && pytest tests/ --cov=app --cov-report=term-missing -v

# Backend — lint
cd validator-agent && ruff check .
cd validator-agent && ruff format --check .

# Backend — run FastAPI server
cd validator-agent && uvicorn app.server:fastapi_app --host 0.0.0.0 --port 8080

# Backend — run agent locally (ADK)
cd validator-agent && adk web
cd validator-agent && adk run app

# Frontend — install dependencies
cd webapp && npm install

# Frontend — dev server
cd webapp && npm run dev

# Frontend — production build
cd webapp && npm run build

# Frontend — run tests
cd webapp && npx vitest run
```

## Project Structure

```
stanford-plan-a/
├── prd_plan_a.json               # Story tracking (phases 1-6)
├── progress-prd_plan_a.txt       # Ralph iteration log
├── CLAUDE.md                     # This file — project conventions
├── scripts/ralph/                # Ralph autonomous loop
│   ├── ralph.sh                  # Loop orchestrator
│   └── ralph-prompt.md           # Per-iteration instructions
│
├── validator-agent/              # Python backend (Google ADK + FastAPI)
│   ├── app/                      # Application package
│   │   ├── __init__.py           # Exports root_agent for ADK discovery
│   │   ├── agent.py              # ADK agent setup & runner
│   │   ├── models.py             # PipelineState Pydantic model
│   │   ├── callbacks.py          # ADK lifecycle callbacks
│   │   ├── server.py             # FastAPI server (ag-ui-adk SSE + REST)
│   │   ├── agents/               # Agent definitions
│   │   │   ├── __init__.py       # Exports all agents
│   │   │   ├── root_agent.py     # Root orchestrator (SpreadsheetValidatorAgent)
│   │   │   ├── ingestion.py      # IngestionAgent — file upload & CSV/XLSX reading
│   │   │   ├── validation.py     # ValidationAgent — business rules + fix cycle
│   │   │   └── processing.py     # ProcessingAgent — transform & package results
│   │   └── tools/                # FunctionTool implementations
│   │       ├── __init__.py       # Exports all tools
│   │       ├── ingestion.py      # File upload & ingest tools
│   │       ├── validation.py     # Validate, request fix, write fix tools
│   │       └── processing.py     # Transform & package tools
│   ├── tests/                    # Test suite
│   │   ├── foundation/           # Phase 1: scaffold verification tests
│   │   ├── agents/               # Agent unit tests
│   │   ├── tools/                # Tool unit tests + integration
│   │   ├── server/               # Server endpoint tests
│   │   └── e2e/                  # End-to-end smoke tests
│   ├── docs/
│   │   └── phases/               # Phase spec files (source of truth)
│   │       ├── phase-01-*.md     # Foundation & scaffold
│   │       ├── phase-02-*.md     # Agent core
│   │       ├── phase-03-*.md     # Tools
│   │       ├── phase-04-*.md     # Backend / server
│   │       ├── phase-05-*.md     # Infrastructure
│   │       └── phase-06-*.md     # Observability & quality
│   ├── pyproject.toml            # Project config & dependencies
│   ├── Dockerfile                # Multi-stage container build
│   └── .env.example              # Environment variable template
│
└── webapp/                       # Next.js frontend (CopilotKit + AG-UI)
    ├── src/
    │   ├── app/                   # Next.js app router
    │   │   ├── page.tsx           # Main page
    │   │   ├── layout.tsx         # Root layout
    │   │   ├── Providers.tsx      # CopilotKit provider setup
    │   │   └── api/copilotkit/    # CopilotKit API route (proxy to backend)
    │   │       └── route.ts
    │   ├── components/a2ui/       # Custom React card components
    │   │   ├── index.ts           # Exports all cards
    │   │   ├── UploadCard.tsx     # File upload prompt card
    │   │   ├── ValidationCard.tsx # Validation results card
    │   │   ├── ErrorFixCard.tsx   # Error fix request card
    │   │   ├── ProgressCard.tsx   # Pipeline progress card
    │   │   └── ResultsCard.tsx    # Final results card
    │   ├── hooks/
    │   │   └── useA2UIStateRender.ts  # useCoAgentStateRender wrapper
    │   └── lib/
    │       └── types.ts           # Shared TypeScript types
    ├── package.json
    ├── tsconfig.json
    └── next.config.ts
```

## Architecture

### Agent Hierarchy

```
SpreadsheetValidatorAgent (root orchestrator)
├── IngestionAgent     → request_file_upload, ingest_file, ingest_uploaded_file
├── ValidationAgent    → validate_data, request_user_fix, write_fix
└── ProcessingAgent    → transform_data, package_results
```

### Server (`app/server.py`)

FastAPI server at port 8080 with ag-ui-adk SSE:
- `GET /health` — Health check
- `POST /run?thread_id=X` — Pre-create ADK session
- `GET /runs` — List all validation runs
- `GET /runs/{session_id}` — Full run detail
- `POST /upload` — File upload (CSV/XLSX) saved as ADK artifact
- `GET /artifacts/{name}` — Download artifact
- `POST /feedback` — User feedback (thumbs up/down)
- `POST /agent` — AG-UI streaming endpoint (SSE via ag-ui-adk)

### Frontend

CopilotKit + HttpAgent connecting to `/agent` SSE endpoint:
- `useCoAgentStateRender` watches agent state and renders React cards
- Custom card components in `src/components/a2ui/`
- No A2UI protocol — pure state-driven rendering
- Agent writes to `state["ui"]` dict, frontend reads and renders matching card

### State Flow

1. Agent tool updates `state["ui"]` with card type + data
2. ag-ui-adk emits `STATE_DELTA` SSE event
3. CopilotKit receives state update
4. `useCoAgentStateRender` triggers re-render with new card
5. User interactions flow back through chat messages

### Pipeline Status Values

| Status | Description |
|--------|-------------|
| `IDLE` | No pipeline running |
| `UPLOADING` | File upload in progress |
| `RUNNING` | Pipeline started |
| `VALIDATING` | Running business rules |
| `WAITING_FOR_USER` | Fix requested, awaiting user input |
| `FIXING` | Applying user's fix |
| `TRANSFORMING` | Adding computed columns |
| `PACKAGING` | Creating output artifacts |
| `COMPLETED` | Pipeline finished successfully |
| `FAILED` | Pipeline encountered an error |

## Configuration

### Google AI Studio (Development)
```bash
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_api_key
```

### Vertex AI (Production)
```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1
```

### Key Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `GOOGLE_API_KEY` | AI Studio API key | — |
| `GOOGLE_CLOUD_PROJECT` | GCP project | — |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `NEXT_PUBLIC_COPILOTKIT_URL` | CopilotKit backend URL | `http://localhost:8080` |

## Key Dependencies

### Backend (Python)
- `google-adk` — Google Agent Development Kit
- `ag-ui-adk` — AG-UI protocol adapter for ADK
- `fastapi` + `uvicorn` — HTTP server
- `pandas` — Data manipulation
- `openpyxl` — Excel file I/O
- `pydantic` — Data models & validation

### Frontend (Node.js)
- `@copilotkit/react-core` — CopilotKit React integration
- `@copilotkit/react-ui` — CopilotKit UI components
- `@ag-ui/client` — AG-UI client (HttpAgent)
- `next` — Next.js framework
- `react` / `react-dom` — React

## Testing

```bash
# Backend — all tests
cd validator-agent && pytest tests/ -v

# Backend — with coverage
cd validator-agent && pytest tests/ --cov=app --cov-report=term-missing -v

# Backend — specific directories
cd validator-agent && pytest tests/foundation/ -v
cd validator-agent && pytest tests/agents/ -v
cd validator-agent && pytest tests/tools/ -v
cd validator-agent && pytest tests/server/ -v
cd validator-agent && pytest tests/e2e/ -v

# Frontend — all tests
cd webapp && npx vitest run

# Frontend — watch mode
cd webapp && npx vitest

# Lint
cd validator-agent && ruff check . && ruff format --check .
```

### Coverage Targets
- Unit: >=80% line coverage for new Python modules
- Integration: All critical paths exercised
- Frontend: Component rendering + state-driven card tests

## Development Guidelines

### Adding Tools

1. Create function in `app/tools/`:
   ```python
   def new_tool(tool_context: ToolContext, param: str) -> dict:
       """Tool description."""
       return {"status": "success"}
   ```
2. Export from `app/tools/__init__.py`
3. Add to appropriate agent's tools list
4. Write tests in `tests/tools/`

### Adding Agents

1. Create agent in `app/agents/`:
   ```python
   from google.adk import LlmAgent
   new_agent = LlmAgent(name="NewAgent", model="gemini-2.0-flash", ...)
   ```
2. Export from `app/agents/__init__.py`
3. Add as sub-agent to root if needed
4. Write tests in `tests/agents/`

### Adding Frontend Cards

1. Create component in `webapp/src/components/a2ui/`:
   ```tsx
   export function NewCard({ data }: { data: NewCardData }) {
     return <div>...</div>;
   }
   ```
2. Export from `webapp/src/components/a2ui/index.ts`
3. Register in `useA2UIStateRender` hook
4. Write tests with vitest

### Code Style

- Python: PEP 8 via ruff, type hints on all functions, docstrings on public APIs
- TypeScript: Strict mode, named exports, functional components
- `ruff check .` and `ruff format --check .` before committing (Python)
- `npm run build` must succeed before committing (frontend)

### TDD Process

Every story follows RED -> GREEN -> REFACTOR:
1. **RED**: Write failing tests from spec
2. **GREEN**: Implement minimum code to pass
3. **REFACTOR**: Clean up, maintain passing tests

## Deployment

### Docker (Backend)
```bash
cd validator-agent
docker build -t spreadsheet-validator .
docker run -p 8080:8080 -e GOOGLE_API_KEY=your_key spreadsheet-validator
```

### Health Check
```bash
curl http://localhost:8080/health
```

## Key Design Decisions

- **No A2UI protocol** — We do NOT use the A2UI render tool or monkey-patch approach. All UI rendering is driven by agent state changes flowing through `useCoAgentStateRender`.
- **No `render_a2ui` tool** — The agent does not call a special render tool. Instead, tools update `state["ui"]` and the frontend reacts to state deltas.
- **ag-ui-adk for SSE** — The `ag-ui-adk` library bridges Google ADK agent execution to AG-UI SSE events consumed by CopilotKit.
- **CopilotKit as UI layer** — Provides chat interface, state synchronization, and the `useCoAgentStateRender` hook for card rendering.
