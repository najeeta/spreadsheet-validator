"""Tests for app.run_manager — RunManager and RunContext."""

import pytest

from app.run_manager import RunContext, RunManager


class TestRunContext:
    def test_defaults(self):
        ctx = RunContext(run_id="test-1")
        assert ctx.run_id == "test-1"
        assert ctx.task is None
        assert ctx.error is None
        assert ctx.completed is False
        assert not ctx.resume_event.is_set()

    def test_resume_event(self):
        ctx = RunContext(run_id="test-2")
        assert not ctx.resume_event.is_set()
        ctx.resume_event.set()
        assert ctx.resume_event.is_set()
        ctx.resume_event.clear()
        assert not ctx.resume_event.is_set()


class TestRunManager:
    def test_create_run(self):
        mgr = RunManager()
        ctx = mgr.create_run("run-1")
        assert ctx.run_id == "run-1"

    def test_get_run(self):
        mgr = RunManager()
        mgr.create_run("run-1")
        ctx = mgr.get_run("run-1")
        assert ctx is not None
        assert ctx.run_id == "run-1"

    def test_get_run_not_found(self):
        mgr = RunManager()
        assert mgr.get_run("nonexistent") is None

    def test_duplicate_run_raises(self):
        mgr = RunManager()
        mgr.create_run("run-1")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_run("run-1")

    def test_signal_resume(self):
        mgr = RunManager()
        ctx = mgr.create_run("run-1")
        assert not ctx.resume_event.is_set()
        mgr.signal_resume("run-1")
        assert ctx.resume_event.is_set()

    def test_signal_resume_nonexistent_no_error(self):
        """Signalling a non-existent run should not raise."""
        mgr = RunManager()
        mgr.signal_resume("no-such-run")  # Should not raise

    def test_remove_run(self):
        mgr = RunManager()
        mgr.create_run("run-1")
        mgr.remove_run("run-1")
        assert mgr.get_run("run-1") is None

    def test_remove_run_nonexistent_no_error(self):
        mgr = RunManager()
        mgr.remove_run("no-such-run")  # Should not raise

    def test_multiple_runs(self):
        mgr = RunManager()
        mgr.create_run("run-1")
        mgr.create_run("run-2")
        assert mgr.get_run("run-1") is not None
        assert mgr.get_run("run-2") is not None
        mgr.remove_run("run-1")
        assert mgr.get_run("run-1") is None
        assert mgr.get_run("run-2") is not None
