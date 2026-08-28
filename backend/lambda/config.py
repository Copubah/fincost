"""Runtime configuration for S3 discovery and bucket analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass


MEBIBYTE = 1024 * 1024
GIBIBYTE = 1024 * 1024 * 1024


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class AnalysisConfig:
    large_object_mb: int
    age_30_days: int
    age_90_days: int
    age_180_days: int
    age_365_days: int
    max_large_object_samples: int

    @property
    def large_object_bytes(self) -> int:
        return self.large_object_mb * MEBIBYTE

    @classmethod
    def from_environment(cls) -> "AnalysisConfig":
        return cls(
            large_object_mb=_positive_int("LARGE_OBJECT_MB", 500),
            age_30_days=_positive_int("AGE_30_DAYS", 30),
            age_90_days=_positive_int("AGE_90_DAYS", 90),
            age_180_days=_positive_int("AGE_180_DAYS", 180),
            age_365_days=_positive_int("AGE_365_DAYS", 365),
            max_large_object_samples=_positive_int("MAX_LARGE_OBJECT_SAMPLES", 100),
        )
