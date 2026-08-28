"""Read-only S3 bucket discovery and object-summary analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

from botocore.exceptions import BotoCoreError, ClientError

from config import AnalysisConfig, GIBIBYTE, MEBIBYTE


KNOWN_STORAGE_CLASSES = {"STANDARD", "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER", "GLACIER_IR", "DEEP_ARCHIVE"}
LEGACY_REGION_ALIASES = {None: "us-east-1", "EU": "eu-west-1"}


def iter_buckets(s3_client: Any) -> Iterator[dict[str, Any]]:
    paginator = s3_client.get_paginator("list_buckets")
    for page in paginator.paginate():
        yield from page.get("Buckets", [])


def get_bucket_region(s3_client: Any, bucket_name: str) -> str:
    location = s3_client.get_bucket_location(Bucket=bucket_name).get("LocationConstraint")
    return LEGACY_REGION_ALIASES.get(location, location or "unknown")


def age_days(last_modified: datetime, now: datetime | None = None) -> int:
    reference = now or datetime.now(timezone.utc)
    timestamp = last_modified if last_modified.tzinfo else last_modified.replace(tzinfo=timezone.utc)
    return max(0, (reference - timestamp.astimezone(timezone.utc)).days)


def age_category(days: int, config: AnalysisConfig) -> str:
    if days < config.age_30_days:
        return f"<{config.age_30_days}_days"
    if days < config.age_90_days:
        return f"{config.age_30_days}-{config.age_90_days - 1}_days"
    if days < config.age_180_days:
        return f"{config.age_90_days}-{config.age_180_days - 1}_days"
    if days < config.age_365_days:
        return f"{config.age_180_days}-{config.age_365_days - 1}_days"
    return f"{config.age_365_days}+_days"


def normalize_storage_class(value: str | None) -> str:
    if not value:
        return "STANDARD"
    normalized = str(value).upper()
    return normalized if normalized in KNOWN_STORAGE_CLASSES else f"UNKNOWN:{normalized}"


def analyze_bucket(s3_client: Any, bucket: dict[str, Any], config: AnalysisConfig, now: datetime | None = None) -> dict[str, Any]:
    """Stream object-list pages; no GetObject calls or object bodies are read."""
    reference = now or datetime.now(timezone.utc)
    name = bucket["Name"]
    storage_class_bytes: dict[str, int] = {}
    age_breakdown: dict[str, int] = {}
    large_objects: list[dict[str, Any]] = []
    object_count = total_size_bytes = 0
    region = get_bucket_region(s3_client, name)
    for page in s3_client.get_paginator("list_objects_v2").paginate(Bucket=name):
        for item in page.get("Contents", []):
            size = int(item.get("Size", 0))
            storage_class = normalize_storage_class(item.get("StorageClass"))
            last_modified = item.get("LastModified", reference)
            days = age_days(last_modified, reference)
            object_count += 1
            total_size_bytes += size
            storage_class_bytes[storage_class] = storage_class_bytes.get(storage_class, 0) + size
            category = age_category(days, config)
            age_breakdown[category] = age_breakdown.get(category, 0) + 1
            if size >= config.large_object_bytes and len(large_objects) < config.max_large_object_samples:
                large_objects.append({"key": item.get("Key", ""), "size": size, "storage_class": storage_class, "last_modified": last_modified.isoformat()})
    return {
        "bucket": name,
        "region": region,
        "creation_date": bucket.get("CreationDate", reference).isoformat(),
        "object_count": object_count,
        "total_size_bytes": total_size_bytes,
        "total_size_mb": round(total_size_bytes / MEBIBYTE, 4),
        "total_size_gb": round(total_size_bytes / GIBIBYTE, 6),
        "storage_class_breakdown": {key: round(value / GIBIBYTE, 6) for key, value in storage_class_bytes.items()},
        "age_breakdown": age_breakdown,
        "large_object_count": len(large_objects),
        "large_objects": large_objects,
    }


def is_bucket_error(error: Exception) -> bool:
    return isinstance(error, (ClientError, BotoCoreError))
