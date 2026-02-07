"""ProcessingAgent — transforms data and packages results into Excel artifacts."""

from google.adk.agents import LlmAgent

from app.callbacks import before_model_modifier
from app.tools.processing import package_results, transform_data


processing_agent = LlmAgent(
    name="process_results",
    description="Transforming data and packaging results",
    model="gemini-2.0-flash",
    before_model_callback=before_model_modifier,
    instruction="""You are the Processing Agent. Your job is to transform validated data
and package results into downloadable Excel files.

Workflow:
1. If the root agent requests additional transformations, call transform_data. Three modes:
   a. Map lookup: lookup_field + lookup_map to derive values from a mapping.
   b. Expression: per-row computation.
   c. Static: default_value for a constant column.
2. Call package_results to create success.xlsx and errors.xlsx.
   package_results automatically adds three computed columns:
   - amount_usd: amount * fx_rate
   - cost_center: mapped from dept via DEFAULT_COST_CENTER_MAP
   - approval_required: YES if dept=FIN and amount > 50k, else NO
   transform_data is still available for additional user-requested transforms.
3. Report artifact names and summary statistics to the user in plain natural language.
   NEVER output raw JSON or tool return values. Summarize results conversationally
   (e.g. "Packaged 15 valid rows into success.xlsx and 2 error rows into errors.xlsx.").
4. Transfer control back to the root agent.""",
    tools=[transform_data, package_results],
    output_key="processing_result",
)
