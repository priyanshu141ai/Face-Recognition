import hashlib
from typing import Any

from app.schemas.face import FaceDetectionSchema
from app.services.detector_base import BaseFaceDetector


class MockFaceDetector(BaseFaceDetector):
    def detect(self, image: bytes) -> list[FaceDetectionSchema]:
        digest = hashlib.sha256(image).hexdigest()
        base = int(digest[:8], 16) % 100
        return [
            FaceDetectionSchema(
                bbox_xywh=[10 + base % 20, 10 + (base // 10), 80.0, 80.0],
                landmarks5=[[20.0 + base, 30.0], [40.0 + base, 30.0], [30.0 + base, 45.0], [22.0 + base, 60.0], [38.0 + base, 60.0]],
                detection_confidence=0.99,
            )
        ]
