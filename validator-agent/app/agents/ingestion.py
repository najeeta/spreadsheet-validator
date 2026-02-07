"""IngestionAgent — confirms file upload and signals readiness.

Used as an AgentTool by the root agent. The upload endpoint handles
actual file parsing; this agent just validates state and transitions status.
"""

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from app.callbacks import before_model_modifier, on_before_agent
from app.tools.ingestion import (
    confirm_ingestion,
    ingest_file,
    ingest_uploaded_file,
    request_file_upload,
)


class IngestionInput(BaseModel):
    """Input for the ingestion agent."""

    file_name: str = Field(default="", description="Name of the uploaded file to process")


ingestion_agent = LlmAgent(
    name="load_spreadsheet",
    description="Loading and parsing uploaded spreadsheet file",
    model="gemini-2.0-flash",
    input_schema=IngestionInput,
    instruction="""You are the Ingestion Agent. Your job is to ensure spreadsheet
data is loaded and ready for validation.

## Workflow
1. **Check Context**: Look for a 'file_name' in your context or state.
2. **Ingest**: If a 'file_name' is present but no data is loaded (row_count is missing or 0):
   - Call **ingest_uploaded_file(file_name=...)**.
   - You can specify `header_row` if you suspect the header isn't on row 0.
3. **Confirm**: Once ingestion is successful (or if data was already loaded),
   - Call **confirm_ingestion** to verify state and transition to RUNNING.
4. **Missing File**: If NO 'file_name' is found and NO data is loaded:
   - Call **request_file_upload**.

## Important
- The upload endpoint saves the file as an artifact but does NOT parse it automatically anymore.
- You MUST call `ingest_uploaded_file` to parse the artifact into state.
- NEVER call `ingest_file` for user uploads — that tool is for local disk paths only.
- Keep responses brief.""",
    tools=[confirm_ingestion, request_file_upload, ingest_uploaded_file, ingest_file],
    before_agent_callback=on_before_agent,
    before_model_callback=before_model_modifier,
    output_key="ingestion_result",
)
