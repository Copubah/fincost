"""EventBridge Lambda entry point for safe, read-only S3 discovery."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from config import AnalysisConfig
from s3_analyzer import analyze_bucket, is_bucket_error, iter_buckets


LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
METRICS_NAMESPACE = "S3StorageOptimizer"


def _emit_metric(name: str, value: float, unit: str = "Count") -> None:
    boto3.client("cloudwatch").put_metric_data(
        Namespace=METRICS_NAMESPACE,
        MetricData=[{"MetricName": name, "Value": value, "Unit": unit}],
    )


def _to_decimal(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_decimal(item) for item in value]
    return value


def _persist_bucket_result(table: Any, scan_id: str, timestamp: str, result: dict[str, Any]) -> None:
    """Persist compact bucket summaries, never complete object listings."""
    item = {
        "scan_id": scan_id,
        "record_key": f"BUCKET#{result['bucket']}",
        "timestamp": timestamp,
        "bucket": result["bucket"],
        "region": result["region"],
        "object_count": result["object_count"],
        "total_size_bytes": result["total_size_bytes"],
        "total_size_gb": result["total_size_gb"],
        "storage_class_breakdown": result["storage_class_breakdown"],
        "large_object_count": result["large_object_count"],
    }
    table.put_item(Item=_to_decimal(item))


def _public_bucket_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": result["bucket"],
        "region": result["region"],
        "creation_date": result["creation_date"],
        "object_count": result["object_count"],
        "total_size_bytes": result["total_size_bytes"],
        "total_size_mb": result["total_size_mb"],
        "total_size_gb": result["total_size_gb"],
        "storage_classes": result["storage_class_breakdown"],
        "large_object_count": result["large_object_count"],
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Discover accessible buckets and persist metadata-only summaries."""
    del event
    started_at = time.monotonic()
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    table_name = os.getenv("ANALYSIS_TABLE_NAME")
    if not table_name:
        LOGGER.error(json.dumps({"message": "scan_configuration_error", "scan_id": scan_id}))
        return {"statusCode": 500, "scan_id": scan_id, "timestamp": timestamp, "status": "configuration_error"}

    config = AnalysisConfig.from_environment()
    LOGGER.info(json.dumps({"message": "scan_started", "scan_id": scan_id}))
    s3_client = boto3.client("s3")
    table = boto3.resource("dynamodb").Table(table_name)
    bucket_results: list[dict[str, Any]] = []
    bucket_failures: list[dict[str, str]] = []
    try:
        for bucket in iter_buckets(s3_client):
            bucket_name = bucket.get("Name", "unknown")
            try:
                result = analyze_bucket(s3_client, bucket, config)
                _persist_bucket_result(table, scan_id, timestamp, result)
                bucket_results.append(_public_bucket_result(result))
            except Exception as error:
                if not is_bucket_error(error):
                    raise
                error_code = getattr(error, "response", {}).get("Error", {}).get("Code", type(error).__name__)
                bucket_failures.append({"bucket": bucket_name, "error": str(error_code)})
                LOGGER.warning(json.dumps({"message": "bucket_skipped", "bucket": bucket_name, "error": str(error_code)}))
        total_objects = sum(item["object_count"] for item in bucket_results)
        total_storage_gb = round(sum(item["total_size_gb"] for item in bucket_results), 6)
        _emit_metric("BucketsScanned", len(bucket_results))
        _emit_metric("ObjectsAnalyzed", total_objects)
        _emit_metric("ScanErrors", len(bucket_failures))
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        LOGGER.info(json.dumps({"message": "scan_completed", "scan_id": scan_id, "buckets_scanned": len(bucket_results), "objects_analyzed": total_objects, "duration_ms": duration_ms}))
        return {"statusCode": 200, "scan_id": scan_id, "timestamp": timestamp, "status": "completed", "buckets_scanned": len(bucket_results), "buckets_failed": len(bucket_failures), "total_objects": total_objects, "total_storage_gb": total_storage_gb, "buckets": bucket_results, "failures": bucket_failures}
    except Exception:
        _emit_metric("ScanErrors", 1)
        LOGGER.exception("scan_failed scan_id=%s", scan_id)
        raise
