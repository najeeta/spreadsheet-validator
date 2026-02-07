"""Shared pytest fixtures for all test layers."""

import os

# Force development mode for tests — must be set before app.services is imported,
# otherwise load_dotenv() in services.py may read ENVIRONMENT=production from .env.
os.environ.setdefault("ENVIRONMENT", "development")
