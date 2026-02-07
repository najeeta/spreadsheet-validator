"""Shared utility functions."""

import hashlib
import io
import json
from typing import Any, Dict, List, Tuple

import pandas as pd


def parse_file(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse a CSV or Excel file into records and columns.

    Args:
        content: The file content as bytes.
        filename: The name of the file (used to determine extension).

    Returns:
        A tuple containing:
        - records: List of dictionaries representing the rows.
        - columns: List of column names.

    Raises:
        ValueError: If the file type is unsupported or parsing fails.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(content))
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise ValueError(f"Unsupported file type: .{ext}")

        # sanitize: replace NaN with None for JSON compatibility
        df = df.astype(object).where(df.notna(), None)

        records = df.to_dict(orient="records")
        columns = list(df.columns)
        return records, columns

    except Exception as e:
        # Wrap all parsing errors in a consistent ValueError
        raise ValueError(f"Failed to parse file: {e}")


def canonicalize_row(row: Dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, None→"null", NaN→"null", floats rounded to 6 decimals.

    Args:
        row: A dictionary representing a data row.

    Returns:
        A canonical JSON string representation of the row.
    """

    def normalize(v: Any) -> Any:
        if v is None:
            return "null"
        # Check for NaN: NaN != NaN is True
        if isinstance(v, float) and v != v:
            return "null"
        if isinstance(v, float):
            return round(v, 6)
        return str(v)

    normalized = {k: normalize(v) for k, v in sorted(row.items())}
    return json.dumps(normalized, sort_keys=True)


def compute_row_fingerprint(row: Dict[str, Any]) -> str:
    """Compute SHA-256 hex digest of a canonicalized row.

    Args:
        row: A dictionary representing a data row.

    Returns:
        64-character hex string (SHA-256 digest).
    """
    canonical = canonicalize_row(row)
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_all_fingerprints(records: List[Dict[str, Any]]) -> List[str]:
    """Compute fingerprints for all rows, parallel to records list.

    Args:
        records: List of row dictionaries.

    Returns:
        List of fingerprint strings, same length as records.
    """
    return [compute_row_fingerprint(r) for r in records]
