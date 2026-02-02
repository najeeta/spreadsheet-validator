"""Tests for project scaffold — Story 1.1."""

import importlib
import pathlib


def test_app_package_importable():
    """Importing app should succeed without errors."""
    mod = importlib.import_module("app")
    assert mod is not None


def test_pyproject_toml_exists():
    """pyproject.toml must exist at the project root."""
    root = pathlib.Path(__file__).resolve().parents[2]
    assert (root / "pyproject.toml").is_file()


def test_app_agents_package_importable():
    """app.agents sub-package should be importable."""
    mod = importlib.import_module("app.agents")
    assert mod is not None


def test_app_tools_package_importable():
    """app.tools sub-package should be importable."""
    mod = importlib.import_module("app.tools")
    assert mod is not None


def test_env_example_exists():
    """.env.example must exist at the project root."""
    root = pathlib.Path(__file__).resolve().parents[2]
    assert (root / ".env.example").is_file()
