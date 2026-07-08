from abc import ABC, abstractmethod

from app.schemas.face import FaceDetectionSchema


class BaseFaceDetector(ABC):
    @abstractmethod
    def detect(self, image: bytes) -> list[FaceDetectionSchema]:
        raise NotImplementedError
