from abc import ABC, abstractmethod
from typing import Any

from app.schemas.face import FaceDetectionSchema


class BaseFaceDetector(ABC):
    @abstractmethod
    def detect(self, image: bytes, quality_policy: Any | None = None) -> list[FaceDetectionSchema]:
        raise NotImplementedError
