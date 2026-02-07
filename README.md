# SpreadsheetValidator

A spreadsheet validation pipeline powered by Google ADK agents, served over AG-UI SSE, with a Next.js + CopilotKit frontend. Users upload a CSV or Excel file, the agent validates it against business rules, walks the user through fixes in a human-in-the-loop cycle, then produces clean output artifacts.

---

## Table of Contents

- [Agent Architecture](#agent-architecture)
  - [Agent Hierarchy](#agent-hierarchy)
  - [Tools](#tools)
  - [Pipeline Workflow](#pipeline-workflow)
- [Local Setup](#local-setup)
- [Cloud Architecture](#cloud-architecture)
- [Deployment](#deployment)
  - [Prerequisites](#prerequisites)
  - [Deploy to Cloud Run](#deploy-to-cloud-run)
  - [Environment Variables](#environment-variables)
- [Next Steps & Improvements](#next-steps--improvements)

---

## Agent Architecture

### Agent Hierarchy

The system uses a root orchestrator with three specialized sub-agents, all running `gemini-2.0-flash`:

```
SpreadsheetValidatorAgent (root orchestrator)
│
├── IngestionAgent
│   Handles file detection, upload prompts, and CSV/XLSX parsing.
│   Registered as AgentTool "load_spreadsheet" on the root agent.
│
├── ValidationAgent
│   Runs 7 business rules + duplicate detection against the ingested data.
│   Batches errors in groups of 5 rows for human review.
│   Registered as AgentTool "validate_data" on the root agent.
│
└── ProcessingAgent
    Adds computed columns (amount_usd, cost_center, approval_required),
    then packages results into success.xlsx and errors.xlsx artifacts.
    Registered as AgentTool "process_results" on the root agent.
```

The root agent delegates to each sub-agent via `AgentTool` wrappers. Each sub-agent operates within a child session that inherits the parent's `PipelineState`, runs its tools, updates state, and returns control to the root.

### Tools

| Tool | Agent | Purpose |
|------|-------|---------|
| `request_file_upload` | Ingestion | Sets status to `UPLOADING`, signals frontend to show upload UI |
| `ingest_uploaded_file` | Ingestion | Parses the uploaded artifact (CSV/XLSX) into dataframe records |
| `ingest_file` | Ingestion | Loads a file from local disk (development/testing) |
| `confirm_ingestion` | Ingestion | Verifies data is loaded, transitions status to `RUNNING` |
| `validate_data` | Validation | Runs all business rules, populates `pending_review` |
| `write_fix` | Validation | Applies a single cell fix from the user |
| `batch_write_fixes` | Validation | Applies multiple fixes to one row at once |
| `skip_row` | Validation | Skips a row's fixes (moves to `skipped_fixes`) |
| `skip_fixes` | Validation | Skips all remaining fixes, resumes pipeline |
| `transform_data` | Processing | Adds a computed column (lookup or expression) |
| `package_results` | Processing | Creates success.xlsx and errors.xlsx, stores as base64 artifacts |

**Business Rules** (enforced by `validate_data`):

1. `employee_id` -- Must match `^[A-Z0-9]{4,12}$`
2. `dept` -- Must be one of `FIN`, `HR`, `ENG`, `OPS`
3. `amount` -- Must be > 0 and <= 100,000
4. `currency` -- Must be `USD`, `EUR`, `GBP`, or `INR`
5. `spend_date` -- Must be `YYYY-MM-DD`, not in the future
6. `vendor` -- Must not be empty
7. `fx_rate` -- Required for non-USD currencies, must be in [0.1, 500]
8. Duplicate check -- `(employee_id, spend_date)` pair must be unique

### Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User opens app                              │
│                              │                                      │
│                    POST /run -> session created                      │
│                    Redirect to /runs/{session_id}                   │
│                              │                                      │
│                 ┌────────────▼────────────┐                         │
│                 │    IDLE - Setup Phase    │                         │
│                 │  Upload file, configure  │                         │
│                 │  cost centers, as_of     │                         │
│                 └────────────┬────────────┘                         │
│                              │ "Start Validation"                   │
│                              ▼                                      │
│                 ┌────────────────────────┐                          │
│                 │   IngestionAgent       │                          │
│                 │  * ingest_uploaded_file │                          │
│                 │  * confirm_ingestion    │                          │
│                 └────────────┬───────────┘                          │
│                              │                                      │
│                              ▼                                      │
│                 ┌────────────────────────┐                          │
│                 │   ValidationAgent      │◄─────────┐               │
│                 │  * validate_data       │          │               │
│                 └────────┬───────────────┘          │               │
│                          │                          │               │
│                    errors found?                    │               │
│                   /            \                    │               │
│                 yes              no                 │               │
│                  │               │                  │               │
│                  ▼               │                  │               │
│   ┌──────────────────────┐      │                  │               │
│   │  WAITING_FOR_USER    │      │                  │               │
│   │  Show pending_review  │      │                  │               │
│   │  (batches of 5 rows) │      │                  │               │
│   └──────────┬───────────┘      │                  │               │
│              │                  │                  │               │
│     User provides fixes         │                  │               │
│     (write_fix / skip)          │                  │               │
│              │                  │                  │               │
│              ▼                  │                  │               │
│   ┌──────────────────────┐      │                  │               │
│   │  All fixes applied?  │──────┼─── re-validate ──┘               │
│   └──────────────────────┘      │                                  │
│                                 │                                  │
│                                 ▼                                  │
│                 ┌────────────────────────┐                          │
│                 │   ProcessingAgent      │                          │
│                 │  * transform_data      │                          │
│                 │  * package_results     │                          │
│                 │    (success.xlsx,      │                          │
│                 │     errors.xlsx)       │                          │
│                 └────────────┬───────────┘                          │
│                              │                                      │
│                              ▼                                      │
│                 ┌────────────────────────┐                          │
│                 │      COMPLETED         │                          │
│                 │  Download artifacts    │                          │
│                 └────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

**State synchronization**: Every tool call updates `PipelineState`. The `ag-ui-adk` bridge emits `STATE_DELTA` SSE events which CopilotKit receives. The frontend's `useCoAgentStateRender` hook triggers re-renders, and `renderForState(state)` maps the current status to the appropriate React card component.

---

## Local Setup

### Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/) installed
- **Node.js 18+** with npm
- A **Google AI Studio API key** (free at [aistudio.google.com](https://aistudio.google.com))

### 1. Clone the repo

```bash
git clone <repo-url>
cd stanford-plan-a
```

### 2. Start the backend

```bash
cd validator-agent

# Install dependencies
uv sync

# Create .env from template
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY

# Start the server
uv run uvicorn app.server:fastapi_app --host 0.0.0.0 --port 8080
```

Verify it's running:

```bash
curl http://localhost:8080/health
```

### 3. Start the frontend

```bash
cd webapp

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Use the app

1. The home page creates a new session and redirects to `/runs/{session_id}`
2. Upload a CSV or XLSX file using the left panel
3. Optionally configure the as-of date, USD rounding, and cost center mapping
4. Click **Start Validation**
5. The agent ingests, validates, and surfaces any errors for you to fix
6. Once all fixes are applied (or skipped), the agent packages results
7. Download `success.xlsx` and `errors.xlsx` from the completion card

---

## Cloud Architecture

The webapp always runs locally on the developer's machine. The backend deploys to Google Cloud Run and uses Vertex AI for model inference and GCS for artifact storage.

```
 ┌──────────────────────────────────────────────┐
 │              Developer Machine                │
 │                                               │
 │   ┌───────────────────────────────────┐       │
 │   │   Next.js Webapp (:3000)          │       │
 │   │   CopilotKit + AG-UI client       │       │
 │   └──────────────┬────────────────────┘       │
 │                  │                             │
 └──────────────────┼─────────────────────────────┘
                    │  HTTPS
                    │  SSE (/agent), REST (/upload, /runs, ...)
                    ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                    Google Cloud                               │
 │                                                               │
 │   ┌──────────────────────────────────────┐                    │
 │   │         Cloud Run                    │                    │
 │   │   FastAPI + ag-ui-adk (:8080)        │                    │
 │   │                                      │                    │
 │   │   /agent  - SSE streaming            │                    │
 │   │   /upload - File upload              │                    │
 │   │   /runs   - Session listing          │                    │
 │   │   /health - Health check             │                    │
 │   └──────────┬──────────────┬────────────┘                    │
 │              │              │                                  │
 │              ▼              ▼                                  │
 │   ┌─────────────────┐  ┌──────────────────┐                   │
 │   │   Vertex AI      │  │  Cloud Storage   │                   │
 │   │                  │  │  (GCS Bucket)    │                   │
 │   │  Gemini 2.0      │  │                  │                   │
 │   │  Flash model     │  │  Artifacts:      │                   │
 │   │                  │  │  * uploads        │                   │
 │   │  Session         │  │  * success.xlsx   │                   │
 │   │  Service         │  │  * errors.xlsx    │                   │
 │   └─────────────────┘  └──────────────────┘                   │
 │                                                               │
 └───────────────────────────────────────────────────────────────┘
```

**Key differences between local and production:**

| Concern | Local (development) | Production |
|---------|-------------------|------------|
| Model API | Google AI Studio (API key) | Vertex AI (service account) |
| Sessions | `InMemorySessionService` | `VertexAiSessionService` |
| Artifacts | `InMemoryArtifactService` | `GcsArtifactService` |
| Backend host | `localhost:8080` | Cloud Run URL |

---

## Deployment

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated (`gcloud auth login`)
- Docker configured for GCR (`gcloud auth configure-docker`)
- A GCP project with billing enabled

### Deploy to Cloud Run

The `deploy.sh` script in `validator-agent/` automates the full deployment:

```bash
cd validator-agent

# Set required environment variables
export GOOGLE_CLOUD_PROJECT=your-project-id
export GCS_ARTIFACT_BUCKET=your-artifact-bucket
export AGENT_ENGINE_ID=1234567890123456789   # from: gcloud ai reasoning-engines list

# Optional overrides
export GOOGLE_CLOUD_LOCATION=us-central1     # default
export SERVICE_NAME=spreadsheet-validator    # default
export CORS_ORIGINS="http://localhost:3000"

# Run the deployment
./deploy.sh
```

The script will:

1. Enable required GCP APIs (Cloud Run, Cloud Build, AI Platform, Cloud Storage)
2. Create the GCS bucket if it doesn't exist
3. Grant IAM permissions to the default compute service account
4. Build and push the Docker image to GCR
5. Deploy to Cloud Run with production environment variables
6. Print the service URL

### After Deployment

Update your webapp to point to the Cloud Run URL:

```bash
# In webapp/.env.local
NEXT_PUBLIC_BACKEND_URL=https://spreadsheet-validator-xxxxx-uc.a.run.app
NEXT_PUBLIC_AGENT_URL=https://spreadsheet-validator-xxxxx-uc.a.run.app/agent
```

Then restart the Next.js dev server.

### Docker (Manual)

```bash
cd validator-agent

# Build
docker build --platform linux/amd64 -t spreadsheet-validator .

# Run locally with production config
docker run -p 8080:8080 \
  -e ENVIRONMENT=production \
  -e GOOGLE_GENAI_USE_VERTEXAI=TRUE \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  -e GOOGLE_CLOUD_LOCATION=us-central1 \
  -e AGENT_ENGINE_ID=1234567890123456789 \
  -e GCS_ARTIFACT_BUCKET=your-bucket \
  spreadsheet-validator
```

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `GOOGLE_API_KEY` | Dev only | -- | Google AI Studio API key |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | `FALSE` | Use Vertex AI instead of AI Studio |
| `GOOGLE_CLOUD_PROJECT` | Prod only | -- | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | `us-central1` | GCP region |
| `AGENT_ENGINE_ID` | Prod only | -- | Vertex AI Reasoning Engine numeric ID |
| `GCS_ARTIFACT_BUCKET` | Prod only | -- | GCS bucket for artifacts |
| `CORS_ORIGINS` | No | `*` | Allowed CORS origins |
| `PORT` | No | `8080` | Server port (Cloud Run injects this) |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Next Steps & Improvements

### Deploy the Webapp
The Next.js frontend currently runs locally. It could be deployed to Vercel, Cloud Run, or any static hosting provider. This would require configuring `NEXT_PUBLIC_BACKEND_URL` and `NEXT_PUBLIC_AGENT_URL` as build-time environment variables pointing to the Cloud Run backend, and setting proper CORS origins on the backend to allow the deployed frontend domain.

### Integrate with Vertex AI Agent Engine Memory
Vertex AI Agent Engine supports memory stores that persist across sessions. Integrating this would allow the agent to remember user preferences (cost center mappings, rounding rules) across runs, learn common fix patterns for repeat uploaders, and surface suggestions based on historical validation outcomes.

### Improve the UI
- Add a data preview table so users can see the raw spreadsheet before validation
- Show a diff view of fixes applied vs. original values
- Add drag-and-drop file upload
- Improve mobile responsiveness
- Add real-time progress percentages (rows validated / total rows)

### Configure Infrastructure for Scaling
- Set Cloud Run min instances > 0 to avoid cold starts
- Configure concurrency limits based on expected load
- Add Cloud Armor or API Gateway for rate limiting
- Set up Cloud Monitoring alerts for error rates and latency
- Consider Redis or Memorystore for session caching if in-memory becomes a bottleneck

### Move to Terraform
Replace the `deploy.sh` bash script with Terraform for declarative, version-controlled infrastructure: Cloud Run service definitions with autoscaling policies, GCS bucket with lifecycle rules, IAM bindings for least-privilege service accounts, Vertex AI Reasoning Engine configuration, environment-specific workspaces (staging, production), and state stored in a GCS backend for team collaboration.
