"""IngestionAgent — handles file upload signaling and CSV/XLSX parsing."""

from google.adk.agents import LlmAgent

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
