"""EventBridge-triggered entry point for the S3 optimization scanner.

Phase 1 deliberately performs only a safe readiness scan. It records the
invocation and emits operational metrics; later phases add S3 analysis and
DynamoDB persistence. The handler never changes S3 resources.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3


LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
METRICS_NAMESPACE = "S3StorageOptimizer"


def _emit_metric(name: str, value: float) -> None:
    """Publish a single CloudWatch metric without exposing event contents."""
    boto3.client("cloudwatch").put_metric_data(
        Namespace=METRICS_NAMESPACE,
        MetricData=[
            {
                "MetricName": name,
                "Value": value,
                "Unit": "Count",
            }
        ],
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle a scheduled or manual scan request.

    The event is intentionally not logged because it may later contain user
    supplied scan parameters. A unique scan id is returned for traceability.
    """
    del event
    started_at = time.monotonic()
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    table_name = os.getenv("ANALYSIS_TABLE_NAME")

    if not table_name:
        LOGGER.error(
            json.dumps(
                {
                    "message": "scan_configuration_error",
                    "scan_id": scan_id,
                    "missing_configuration": "ANALYSIS_TABLE_NAME",
                }
            )
        )
        return {
            "statusCode": 500,
            "scan_id": scan_id,
            "timestamp": timestamp,
            "status": "configuration_error",
        }

    LOGGER.info(
        json.dumps(
            {
                "message": "scan_started",
                "scan_id": scan_id,
                "analysis_table": table_name,
                "request_id": getattr(context, "aws_request_id", None),
            }
        )
    )

    try:
        # Kept as a dedicated safe boundary for the richer scan workflow.
        _emit_metric("ScansStarted", 1)
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        _emit_metric("ScansCompleted", 1)
        LOGGER.info(
            json.dumps(
                {
                    "message": "scan_completed",
                    "scan_id": scan_id,
                    "duration_ms": duration_ms,
                }
            )
        )
        return {
            "statusCode": 200,
            "scan_id": scan_id,
            "timestamp": timestamp,
            "status": "initialized",
        }
    except Exception:
        _emit_metric("ScanErrors", 1)
        LOGGER.exception("scan_failed scan_id=%s", scan_id)
        raise
