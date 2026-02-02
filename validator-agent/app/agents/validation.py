"""ValidationAgent — enforces 7 business rules and manages fix lifecycle."""

from google.adk.agents import LlmAgent

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
