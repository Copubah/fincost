"""Unit tests for the Phase 1 Lambda entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "lambda"))

import scanner  # noqa: E402


def test_handler_returns_initialized_scan(monkeypatch: object) -> None:
    monkeypatch.setenv("ANALYSIS_TABLE_NAME", "optimizer-dev-analysis")
    cloudwatch = Mock()
    context = Mock(aws_request_id="request-123")

    with patch.object(scanner.boto3, "client", return_value=cloudwatch):
        result = scanner.lambda_handler({}, context)

    assert result["statusCode"] == 200
    assert result["status"] == "initialized"
    assert result["scan_id"]
    assert cloudwatch.put_metric_data.call_count == 2


def test_handler_returns_safe_error_when_table_name_is_missing(
    monkeypatch: object,
) -> None:
    monkeypatch.delenv("ANALYSIS_TABLE_NAME", raising=False)

    result = scanner.lambda_handler({}, Mock(aws_request_id="request-456"))

    assert result["statusCode"] == 500
    assert result["status"] == "configuration_error"
    assert result["scan_id"]
