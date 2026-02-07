"""ValidationAgent — enforces 7 business rules, called as an agent tool by root."""

from google.adk.agents import LlmAgent

from app.callbacks import before_model_modifier
from app.tools.validation import validate_data


validation_agent = LlmAgent(
    name="validate_data",
    description="Validating data against business rules",
    model="gemini-2.0-flash",
    before_model_callback=before_model_modifier,
    instruction="""You are the Validation Agent. Your job is to validate spreadsheet data
against business rules.

## Workflow
1. Call validate_data to check all records against 7 business rules.
2. Return the validation result (error count, valid count, total rows).

The validate_data tool automatically populates pending_review and sets status
to WAITING_FOR_USER when errors are found. The root agent handles the HITL
fix cycle — you do NOT need to handle fixes or interact with the user.

## Business Rules
- employee_id: Must match EMP followed by 3+ digits, must be unique
- dept: Must be a valid department (Engineering, Marketing, Sales, etc.)
- amount: Must be > 0 and <= 100,000
- currency: Must be a valid ISO 4217 code
- spend_date: Must be YYYY-MM-DD format and not in the future
- vendor: Must not be empty
- fx_rate: Required for non-USD currencies, must be in [0.1, 500]""",
    tools=[validate_data],
    output_key="validation_result",
)
