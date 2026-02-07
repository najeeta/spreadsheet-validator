"""Tests for app.api_models — Pydantic request/response models."""

import pytest
from pydantic import ValidationError

from app.api_models import (
    AnswerRequest,
    AnswerResponse,
    CreateRunResponse,
    RowFixes,
    SingleFix,
)


class TestCreateRunResponse:
    def test_valid(self):
        r = CreateRunResponse(run_id="abc-123", status="RUNNING")
        assert r.run_id == "abc-123"
        assert r.status == "RUNNING"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            CreateRunResponse(run_id="abc")


class TestSingleFix:
    def test_valid(self):
        f = SingleFix(row_index=0, field="dept", new_value="ENG")
        assert f.row_index == 0
        assert f.field == "dept"
        assert f.new_value == "ENG"

    def test_new_value_any_type(self):
        f = SingleFix(row_index=1, field="amount", new_value=1500.50)
        assert f.new_value == 1500.50

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            SingleFix(row_index=0, new_value="ENG")


class TestRowFixes:
    def test_valid(self):
        rf = RowFixes(row_index=0, fixes={"dept": "ENG", "vendor": "Acme"})
        assert rf.row_index == 0
        assert rf.fixes == {"dept": "ENG", "vendor": "Acme"}

    def test_missing_fixes(self):
        with pytest.raises(ValidationError):
            RowFixes(row_index=0)


class TestAnswerRequest:
    def test_empty_body(self):
        """Empty body is valid — represents a no-op."""
        r = AnswerRequest()
        assert r.fixes is None
        assert r.row_fixes is None
        assert r.skip_rows is None
        assert r.skip_all is False

    def test_skip_all(self):
        r = AnswerRequest(skip_all=True)
        assert r.skip_all is True

    def test_with_fixes(self):
        r = AnswerRequest(
            fixes=[
                SingleFix(row_index=0, field="dept", new_value="ENG"),
            ]
        )
        assert len(r.fixes) == 1

    def test_with_row_fixes(self):
        r = AnswerRequest(
            row_fixes=[
                RowFixes(row_index=0, fixes={"dept": "ENG"}),
            ]
        )
        assert len(r.row_fixes) == 1

    def test_with_skip_rows(self):
        r = AnswerRequest(skip_rows=[0, 1, 2])
        assert r.skip_rows == [0, 1, 2]

    def test_combined(self):
        r = AnswerRequest(
            fixes=[SingleFix(row_index=0, field="dept", new_value="ENG")],
            skip_rows=[5],
        )
        assert len(r.fixes) == 1
        assert r.skip_rows == [5]


class TestAnswerResponse:
    def test_valid(self):
        r = AnswerResponse(
            status="RUNNING",
            pending_fixes_count=0,
            remaining_fixes_count=0,
            skipped_count=2,
            applied_count=3,
            message="Applied 3 fixes, skipped 2 rows.",
        )
        assert r.status == "RUNNING"
        assert r.applied_count == 3

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            AnswerResponse(status="RUNNING")
