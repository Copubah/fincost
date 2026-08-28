"""Unit tests for scanner orchestration and DynamoDB persistence."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parents[1] / "lambda"))

import scanner  # noqa: E402


def test_handler_persists_success_and_continues_after_access_denied(monkeypatch: object) -> None:
    monkeypatch.setenv("ANALYSIS_TABLE_NAME", "optimizer-dev-analysis")
    s3_client, cloudwatch, table, dynamodb = Mock(), Mock(), Mock(), Mock()
    dynamodb.Table.return_value = table
    allowed = {"bucket": "allowed", "region": "us-east-1", "creation_date": "2026-01-01T00:00:00+00:00", "object_count": 2, "total_size_bytes": 30, "total_size_mb": 0.0, "total_size_gb": 0.0, "storage_class_breakdown": {"STANDARD": 0.0}, "large_object_count": 0, "large_objects": []}
    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "ListObjectsV2")
    with patch.object(scanner.boto3, "client", side_effect=[s3_client, cloudwatch, cloudwatch, cloudwatch]), patch.object(scanner.boto3, "resource", return_value=dynamodb), patch.object(scanner, "iter_buckets", return_value=[{"Name": "allowed"}, {"Name": "denied"}]), patch.object(scanner, "analyze_bucket", side_effect=[allowed, denied]):
        response = scanner.lambda_handler({}, Mock(aws_request_id="request-123"))
    assert response["statusCode"] == 200
    assert response["buckets_scanned"] == 1
    assert response["buckets_failed"] == 1
    assert response["failures"] == [{"bucket": "denied", "error": "AccessDenied"}]
    table.put_item.assert_called_once()


def test_handler_returns_safe_error_when_table_name_is_missing(monkeypatch: object) -> None:
    monkeypatch.delenv("ANALYSIS_TABLE_NAME", raising=False)
    result = scanner.lambda_handler({}, Mock(aws_request_id="request-456"))
    assert result["statusCode"] == 500
    assert result["status"] == "configuration_error"
