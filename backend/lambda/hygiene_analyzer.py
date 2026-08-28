"""Read-only lifecycle, security, version, multipart, and duplicate analysis."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError


def finding(kind: str, severity: str, bucket: str, title: str, description: str, recommendation: str, resource: str | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    digest = hashlib.sha256(f"{kind}:{bucket}:{resource or ''}:{title}".encode()).hexdigest()[:16]
    return {"finding_id": f"f-{digest}", "type": kind, "severity": severity, "bucket": bucket, "resource": resource or bucket, "title": title, "description": description, "evidence": evidence or {}, "recommendation": recommendation, "estimated_savings": None}


def analyze_lifecycle(s3: Any, bucket: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        rules = s3.get_bucket_lifecycle_configuration(Bucket=bucket).get("Rules", [])
    except ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
            return {"enabled": False, "rule_count": 0, "transitions": 0, "expirations": 0, "abort_incomplete_multipart": 0, "noncurrent_expirations": 0}, [finding("MISSING_LIFECYCLE_POLICY", "MEDIUM", bucket, "Bucket has no lifecycle policy", "No lifecycle configuration was found.", "Configure lifecycle transitions and cleanup rules.")]
        raise
    summary = {"enabled": bool(rules), "rule_count": len(rules), "transitions": sum(bool(rule.get("Transitions") or rule.get("NoncurrentVersionTransitions")) for rule in rules), "expirations": sum(bool(rule.get("Expiration")) for rule in rules), "abort_incomplete_multipart": sum(bool(rule.get("AbortIncompleteMultipartUpload")) for rule in rules), "noncurrent_expirations": sum(bool(rule.get("NoncurrentVersionExpiration")) for rule in rules)}
    results: list[dict[str, Any]] = []
    for key, title, recommendation in [("transitions", "Lifecycle policy has no archival transition", "Consider transitions for suitable inactive objects."), ("expirations", "Lifecycle policy has no expiration rule", "Review expiration for disposable data."), ("abort_incomplete_multipart", "Lifecycle policy does not abort incomplete uploads", "Abort incomplete multipart uploads after a defined period.")]:
        if not summary[key]: results.append(finding("LIFECYCLE_RULE_QUALITY", "INFO", bucket, title, title, recommendation))
    return summary, results


def analyze_security(s3: Any, bucket: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    try:
        encryption = s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"][0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "ServerSideEncryptionConfigurationNotFoundError": raise
        encryption = "NONE"; findings.append(finding("MISSING_DEFAULT_ENCRYPTION", "HIGH", bucket, "Bucket has no default encryption", "Default encryption is not configured.", "Enable SSE-S3 or SSE-KMS default encryption."))
    try:
        block = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "NoSuchPublicAccessBlockConfiguration": raise
        block = {}
    unsafe = [key for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets") if not block.get(key, False)]
    if unsafe: findings.append(finding("POTENTIALLY_EXPOSED", "HIGH", bucket, "Public access protections are incomplete", "One or more Public Access Block controls are disabled; this is not confirmation of public access.", "Review bucket policy, ACLs, and all Public Access Block settings.", evidence={"disabled_controls": unsafe}))
    return {"encryption": encryption, "public_access_block": block, "potentially_exposed": bool(unsafe)}, findings


def analyze_versions_and_uploads(s3: Any, bucket: str, incomplete_days: int = 7, now: datetime | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reference = now or datetime.now(timezone.utc); findings: list[dict[str, Any]] = []
    status = s3.get_bucket_versioning(Bucket=bucket).get("Status", "Disabled")
    noncurrent_count = noncurrent_bytes = 0
    if status in ("Enabled", "Suspended"):
        for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
            for version in page.get("Versions", []):
                if not version.get("IsLatest", True): noncurrent_count += 1; noncurrent_bytes += int(version.get("Size", 0))
        if noncurrent_count: findings.append(finding("NONCURRENT_VERSIONS", "MEDIUM", bucket, "Bucket contains noncurrent versions", "Noncurrent versions consume storage.", "Configure noncurrent-version lifecycle expiration.", evidence={"count": noncurrent_count, "bytes": noncurrent_bytes}))
    uploads = 0
    for page in s3.get_paginator("list_multipart_uploads").paginate(Bucket=bucket):
        for upload in page.get("Uploads", []):
            age = max(0, (reference - upload["Initiated"].astimezone(timezone.utc)).days)
            if age >= incomplete_days:
                uploads += 1; findings.append(finding("INCOMPLETE_MULTIPART_UPLOAD", "LOW", bucket, "Stale incomplete multipart upload", "An incomplete upload exceeds the configured age threshold.", "Abort incomplete multipart uploads after 7 days.", resource=upload.get("Key"), evidence={"age_days": age}))
    return {"status": status, "noncurrent_version_count": noncurrent_count, "noncurrent_storage_size": noncurrent_bytes, "stale_multipart_uploads": uploads}, findings


def detect_duplicates(objects: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str, str], list[str]] = {}
    for obj in objects:
        etag = str(obj.get("etag", "")).strip('"')
        if etag and "-" not in etag: groups.setdefault((int(obj["size"]), etag, obj.get("storage_class", "STANDARD")), []).append(obj["key"])
    return [finding("POTENTIAL_DUPLICATE", "LOW", bucket, "Potential duplicate objects", "Objects have matching size and ETag metadata; ETag alone is not proof of identical content.", "Review before deleting any object.", evidence={"objects": keys, "reclaimable_bytes": key[0] * (len(keys)-1)}) for key, keys in groups.items() if len(keys) > 1]
