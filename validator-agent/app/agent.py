"""ADK App wrapper for the SpreadsheetValidator agent."""

from google.adk.apps import App

from app.agents.root_agent import root_agent

adk_app = App(
    name="spreadsheet_validator",
    root_agent=root_agent,
)
