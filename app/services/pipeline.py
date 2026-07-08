import time
from typing import Any

import numpy as np

from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.logging import get_logger, log_event
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.schemas.face import FaceDetectionSchema, VerifyRequest
from app.services.calibration import ScoreCalibrator
from app.services.image_decoder import ImageDecoder
from app.services.matcher import FaceMatcher
from app.services.preprocessing import Preprocessor


class FaceVerificationPipeline:
    def __init__(self) -> None:
        self.logger = get_logger("pipeline")
        self.decoder = ImageDecoder()
        self.preprocessor = Preprocessor()
        self.detector = MockFaceDetector()
        self.recognizer = MockFaceRecognizer()
        self.matcher = FaceMatcher()
        self.calibrator = ScoreCalibrator()

    def verify(self, request: VerifyRequest, max_image_mb: float) -> dict[str, Any]:
        timings = {"decode": 0.0, "detect": 0.0, "align": 0.0, "embed": 0.0, "match": 0.0, "total": 0.0}
        start = time.perf_counter()

        image_a_bytes = self._decode_and_validate(request.image_a, max_image_mb, timings)
        image_b_bytes = self._decode_and_validate(request.image_b, max_image_mb, timings)

        detect_start = time.perf_counter()
        detections_a = self.detector.detect(image_a_bytes)
        detections_b = self.detector.detect(image_b_bytes)
        timings["detect"] = round((time.perf_counter() - detect_start) * 1000.0, 2)

        self._validate_quality(detections_a, request.quality_policy, "image_a")
        self._validate_quality(detections_b, request.quality_policy, "image_b")

        align_start = time.perf_counter()
        aligned_a = self.preprocessor.align_face(np.zeros((112, 112, 3), dtype=np.uint8), detections_a[0])
        aligned_b = self.preprocessor.align_face(np.zeros((112, 112, 3), dtype=np.uint8), detections_b[0])
        timings["align"] = round((time.perf_counter() - align_start) * 1000.0, 2)

        embed_start = time.perf_counter()
        emb_a = self.recognizer.embed(aligned_a)
        emb_b = self.recognizer.embed(aligned_b)
        timings["embed"] = round((time.perf_counter() - embed_start) * 1000.0, 2)

        match_start = time.perf_counter()
        similarity = self.matcher.cosine_similarity(emb_a, emb_b)
        decision = self.matcher.decide(similarity)
        timings["match"] = round((time.perf_counter() - match_start) * 1000.0, 2)

        score = self.calibrator.calibrate(similarity)
        timings["total"] = round((time.perf_counter() - start) * 1000.0, 2)
        log_event(
            self.logger,
            request_id=request.request_id,
            endpoint="/v1/faces/verify",
            decision=decision,
            timings=timings,
            model_versions={
                "detector": "mock_yunet_adapter_v1",
                "recognizer": "mock_arcface_adapter_v1",
                "preprocessing": "align112_rgb_mock_v1",
                "calibration": "linear_mock_v1",
            },
        )

        return {
            "request_id": request.request_id,
            "decision": decision,
            "match_score_percent": score,
            "similarity_cosine": round(similarity, 6),
            "threshold": {
                "score_type": "cosine",
                "value": self.matcher.threshold,
                "operating_point": "phase1_mock",
            },
            "model_versions": {
                "detector": "mock_yunet_adapter_v1",
                "recognizer": "mock_arcface_adapter_v1",
                "preprocessing": "align112_rgb_mock_v1",
                "calibration": "linear_mock_v1",
            },
            "faces": {
                "image_a": [detection.model_dump() for detection in detections_a],
                "image_b": [detection.model_dump() for detection in detections_b],
            },
            "timings_ms": timings,
        }

    def _decode_and_validate(self, payload: Any, max_image_mb: float, timings: dict[str, float]) -> bytes:
        decode_start = time.perf_counter()
        decoded = self.decoder.decode(payload.data, payload.kind)
        timings["decode"] += round((time.perf_counter() - decode_start) * 1000.0, 2)
        size_mb = len(decoded) / (1024 * 1024)
        if size_mb > max_image_mb:
            raise InvalidImagePayloadError(f"image exceeds {max_image_mb}MB")
        return decoded

    def _validate_quality(self, detections: list[FaceDetectionSchema], policy: Any, which: str) -> None:
        if not detections:
            if policy.reject_if_no_face:
                raise FaceQualityError("no_face_detected", f"no face detected in {which}")
            return
        if len(detections) > 1 and policy.reject_if_multiple_faces:
            raise FaceQualityError("multiple_faces_detected", f"multiple faces detected in {which}")
        if detections[0].detection_confidence < policy.min_detection_confidence:
            raise FaceQualityError("face_quality_rejected", f"face quality rejected for {which}")
