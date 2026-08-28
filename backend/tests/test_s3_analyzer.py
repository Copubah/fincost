"""Unit tests for paginated, metadata-only S3 analysis."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / "lambda"))

from config import AnalysisConfig, MEBIBYTE  # noqa: E402
from s3_analyzer import age_category, age_days, analyze_bucket, get_bucket_region, iter_buckets, normalize_storage_class  # noqa: E402


def configured() -> AnalysisConfig:
    return AnalysisConfig(500, 30, 90, 180, 365, 100)


def test_bucket_discovery_uses_all_pages() -> None:
    paginator = Mock()
    paginator.paginate.return_value = [{"Buckets": [{"Name": "one"}]}, {"Buckets": [{"Name": "two"}]}]
    client = Mock()
    client.get_paginator.return_value = paginator
    assert [bucket["Name"] for bucket in iter_buckets(client)] == ["one", "two"]
    client.get_paginator.assert_called_once_with("list_buckets")


def test_region_handles_legacy_us_east_value() -> None:
    client = Mock()
    client.get_bucket_location.return_value = {"LocationConstraint": None}
    assert get_bucket_region(client, "example") == "us-east-1"


def test_object_pagination_counts_sizes_and_storage_classes() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    client = Mock()
    client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
    client.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": "a", "Size": 10, "LastModified": now, "ETag": "a"}]},
        {"Contents": [{"Key": "b", "Size": 20, "StorageClass": "STANDARD_IA", "LastModified": now, "ETag": "b"}]},
    ]
    result = analyze_bucket(client, {"Name": "example", "CreationDate": now}, configured(), now)
    assert result["object_count"] == 2
    assert result["total_size_bytes"] == 30
    assert result["storage_class_breakdown"] == {"STANDARD": 0.0, "STANDARD_IA": 0.0}
    assert result["age_breakdown"] == {"<30_days": 2}
    client.get_paginator.assert_called_once_with("list_objects_v2")


def test_large_object_and_object_age_are_detected() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    client = Mock()
    client.get_bucket_location.return_value = {"LocationConstraint": "EU"}
    client.get_paginator.return_value.paginate.return_value = [{"Contents": [{"Key": "archive", "Size": 500 * MEBIBYTE, "StorageClass": "GLACIER", "LastModified": now - timedelta(days=200), "ETag": "etag"}]}]
    result = analyze_bucket(client, {"Name": "example", "CreationDate": now}, configured(), now)
    assert result["region"] == "eu-west-1"
    assert result["large_object_count"] == 1
    assert result["large_objects"][0]["key"] == "archive"
    assert result["age_breakdown"] == {"180-364_days": 1}


def test_age_categories_and_unknown_storage_class_are_safe() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    assert age_days(now - timedelta(days=365), now) == 365
    assert age_category(90, configured()) == "90-179_days"
    assert normalize_storage_class("future_class") == "UNKNOWN:FUTURE_CLASS"
