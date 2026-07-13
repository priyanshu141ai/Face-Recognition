from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LivenessResult:
    approved: bool
    provider: str
    reason_code: str


class LivenessProvider(ABC):
    name: str
    production_capable: bool = False

    @abstractmethod
    def evaluate(
        self,
        frames: list[bytes],
        challenge: dict[str, object],
        provider_assertion: str | None,
        capture_timestamp: str,
    ) -> LivenessResult:
        raise NotImplementedError
