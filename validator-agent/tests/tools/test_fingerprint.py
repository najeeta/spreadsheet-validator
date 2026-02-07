"""Tests for fingerprinting utilities — incremental validation support."""

from app.utils import (
    canonicalize_row,
    compute_all_fingerprints,
    compute_row_fingerprint,
)


class TestCanonicalizeRow:
    """Tests for canonicalize_row function."""

    def test_sorts_keys(self):
        """Keys should be sorted alphabetically."""
        row = {"z": "1", "a": "2", "m": "3"}
        result = canonicalize_row(row)
        # JSON should have keys in sorted order
        assert result.index('"a"') < result.index('"m"') < result.index('"z"')

    def test_handles_none(self):
        """None values should be canonicalized as 'null' string."""
        row = {"field": None}
        result = canonicalize_row(row)
        assert '"field": "null"' in result

    def test_handles_nan(self):
        """NaN values should be canonicalized as 'null' string."""
        row = {"field": float("nan")}
        result = canonicalize_row(row)
        assert '"field": "null"' in result

    def test_rounds_floats(self):
        """Float values should be rounded to 6 decimal places."""
        row = {"amount": 123.456789012345}
        result = canonicalize_row(row)
        # Should be rounded to 123.456789
        assert "123.456789" in result
        # Should NOT contain more precision
        assert "123.4567890123" not in result

    def test_converts_values_to_strings(self):
        """Non-float, non-None values should be converted to strings."""
        row = {"number": 42, "text": "hello"}
        result = canonicalize_row(row)
        assert '"number": "42"' in result
        assert '"text": "hello"' in result


class TestComputeRowFingerprint:
    """Tests for compute_row_fingerprint function."""

    def test_returns_64_hex_chars(self):
        """SHA-256 should produce 64 hex characters."""
        row = {"employee_id": "EMP001", "dept": "Engineering"}
        fp = compute_row_fingerprint(row)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_row_same_fingerprint(self):
        """Identical rows should produce identical fingerprints."""
        row1 = {"employee_id": "EMP001", "dept": "Engineering", "amount": 1000.0}
        row2 = {"employee_id": "EMP001", "dept": "Engineering", "amount": 1000.0}
        assert compute_row_fingerprint(row1) == compute_row_fingerprint(row2)

    def test_different_rows_different_fingerprints(self):
        """Different rows should produce different fingerprints."""
        row1 = {"employee_id": "EMP001", "dept": "Engineering"}
        row2 = {"employee_id": "EMP002", "dept": "Engineering"}
        assert compute_row_fingerprint(row1) != compute_row_fingerprint(row2)

    def test_key_order_independent(self):
        """Fingerprint should be the same regardless of key insertion order."""
        row1 = {"a": "1", "b": "2", "c": "3"}
        row2 = {"c": "3", "a": "1", "b": "2"}
        assert compute_row_fingerprint(row1) == compute_row_fingerprint(row2)

    def test_float_precision_normalized(self):
        """Floats with different precision but same value should match."""
        row1 = {"amount": 1000.0}
        row2 = {"amount": 1000.000000}
        assert compute_row_fingerprint(row1) == compute_row_fingerprint(row2)

    def test_none_and_nan_equivalent(self):
        """None and NaN should produce the same fingerprint."""
        row1 = {"field": None}
        row2 = {"field": float("nan")}
        assert compute_row_fingerprint(row1) == compute_row_fingerprint(row2)


class TestComputeAllFingerprints:
    """Tests for compute_all_fingerprints function."""

    def test_returns_list_same_length(self):
        """Output list should be same length as input."""
        records = [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
        ]
        fps = compute_all_fingerprints(records)
        assert len(fps) == len(records)

    def test_empty_list(self):
        """Empty input should return empty list."""
        assert compute_all_fingerprints([]) == []

    def test_each_fingerprint_is_valid(self):
        """Each fingerprint should be a valid 64-char hex string."""
        records = [{"a": "1"}, {"b": "2"}]
        fps = compute_all_fingerprints(records)
        for fp in fps:
            assert len(fp) == 64
            assert all(c in "0123456789abcdef" for c in fp)

    def test_preserves_order(self):
        """Fingerprints should be parallel to input records."""
        records = [
            {"id": "first"},
            {"id": "second"},
        ]
        fps = compute_all_fingerprints(records)
        # Verify first fingerprint matches first record
        assert fps[0] == compute_row_fingerprint(records[0])
        assert fps[1] == compute_row_fingerprint(records[1])
