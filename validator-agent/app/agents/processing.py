"""ProcessingAgent — transforms data and packages results into Excel artifacts."""

from google.adk.agents import LlmAgent

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
