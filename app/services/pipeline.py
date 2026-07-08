import time
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.errors import DetectorProviderError, FaceQualityError, InvalidImagePayloadError, RecognizerProviderError
from app.core.logging import get_logger, log_event
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.insightface_buffalo_recognizer import InsightFaceBuffaloRecognizer
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.models.mobilefacenet_onnx_recognizer import MobileFaceNetOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.schemas.face import FaceDetectionSchema, VerifyRequest
from app.services.calibration import ScoreCalibrator
from app.services.image_decoder import ImageDecoder
from app.services.matcher import FaceMatcher
from app.services.preprocessing import Preprocessor


class FaceVerificationPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = get_logger("pipeline")
        self.decoder = ImageDecoder()
        self.preprocessor = Preprocessor()
        self.detector = None
        self.recognizer = None
        self.matcher = FaceMatcher(threshold=self.settings.match_threshold)
        self.calibrator = ScoreCalibrator()

    def verify(self, request: VerifyRequest, max_image_mb: float) -> dict[str, Any]:
        timings = {"decode": 0.0, "detect": 0.0, "align": 0.0, "embed": 0.0, "match": 0.0, "total": 0.0}
        start = time.perf_counter()

        image_a_bytes = self._decode_and_validate(request.image_a, max_image_mb, timings)
        image_b_bytes = self._decode_and_validate(request.image_b, max_image_mb, timings)

        detect_start = time.perf_counter()
        detector = self._get_detector()
        raw_detections_a = detector.detect(image_a_bytes, None)
        raw_detections_b = detector.detect(image_b_bytes, None)
        timings["detect"] = round((time.perf_counter() - detect_start) * 1000.0, 2)

        self._validate_quality(raw_detections_a, request.quality_policy, "image_a")
        self._validate_quality(raw_detections_b, request.quality_policy, "image_b")
        detections_a = self._select_faces(raw_detections_a, request.face_selector, request.face_index)
        detections_b = self._select_faces(raw_detections_b, request.face_selector, request.face_index)
        if not detections_a or not detections_b:
            raise FaceQualityError("no_face_detected", "face verification requires one detected face per image")

        align_start = time.perf_counter()
        aligned_a = self.preprocessor.align_face(self._decode_image_bytes(image_a_bytes), detections_a[0])
        aligned_b = self.preprocessor.align_face(self._decode_image_bytes(image_b_bytes), detections_b[0])
        timings["align"] = round((time.perf_counter() - align_start) * 1000.0, 2)

        embed_start = time.perf_counter()
        recognizer = self._get_recognizer()
        emb_a = recognizer.embed(aligned_a)
        emb_b = recognizer.embed(aligned_b)
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
            detector_provider=self.settings.detector_provider,
            recognizer_provider=self.settings.recognizer_provider,
            onnx_providers=self.settings.onnx_providers,
            number_of_faces_detected=len(detections_a),
            selected_face_index=0 if detections_a else None,
            detection_confidence=detections_a[0].detection_confidence if detections_a else None,
            similarity_cosine=round(similarity, 6),
            decision=decision,
            timings_ms=timings,
            model_versions={
                "detector": self._detector_name(),
                "recognizer": self._recognizer_name(),
                "preprocessing": "align112_rgb_v1",
                "calibration": self.calibrator.version,
            },
        )

        payload = {
            "request_id": request.request_id,
            "decision": decision,
            "match_score_percent": score,
            "similarity_cosine": round(similarity, 6),
            "threshold": {
                "score_type": "cosine",
                "value": self.matcher.threshold,
                "operating_point": "phase3_fixed_threshold",
            },
            "model_versions": {
                "detector": self._detector_name(),
                "recognizer": self._recognizer_name(),
                "preprocessing": "align112_rgb_v1",
                "calibration": self.calibrator.version,
            },
            "faces": {
                "image_a": [detection.model_dump() for detection in detections_a],
                "image_b": [detection.model_dump() for detection in detections_b],
            },
            "timings_ms": timings,
        }
        if request.return_embeddings and self.settings.allow_embedding_return:
            payload["embeddings"] = {
                "image_a": emb_a.tolist(),
                "image_b": emb_b.tolist(),
            }
        return payload

    def _get_detector(self):
        if self.detector is None:
            provider = self.settings.detector_provider
            if provider == "yunet":
                self.detector = YuNetFaceDetector()
            elif provider == "mock":
                self.detector = MockFaceDetector()
            else:
                raise DetectorProviderError("detector provider is invalid")
        return self.detector

    def _get_recognizer(self):
        if self.recognizer is None:
            provider = self.settings.recognizer_provider
            if provider == "mock":
                self.recognizer = MockFaceRecognizer()
            elif provider == "arcface_onnx":
                self.recognizer = ArcFaceOnnxRecognizer()
            elif provider == "mobilefacenet_onnx":
                self.recognizer = MobileFaceNetOnnxRecognizer()
            elif provider == "insightface_buffalo_l":
                self.recognizer = InsightFaceBuffaloRecognizer()
            else:
                raise RecognizerProviderError("recognizer provider is invalid")
        return self.recognizer

    def _select_faces(self, detections: list[FaceDetectionSchema], selector: str, face_index: int | None = None) -> list[FaceDetectionSchema]:
        if selector == "all":
            return detections
        if selector == "highest_confidence":
            return [max(detections, key=lambda item: item.detection_confidence)] if detections else []
        if selector == "face_index":
            if face_index is None or face_index < 0 or face_index >= len(detections):
                raise FaceQualityError("face_quality_rejected", "face_index is out of range")
            return [detections[face_index]]
        if selector == "largest":
            return [max(detections, key=lambda item: item.bbox_xywh[2] * item.bbox_xywh[3])] if detections else []
        return detections[:1]

    def _detector_name(self) -> str:
        if self.settings.detector_provider == "yunet":
            return "yunet_2023mar_opencv"
        return "mock_yunet_adapter_v1"

    def _recognizer_name(self) -> str:
        if self.settings.recognizer_provider == "arcface_onnx":
            return "arcface_r100_onnx"
        if self.settings.recognizer_provider == "mobilefacenet_onnx":
            return "mobilefacenet_onnx"
        if self.settings.recognizer_provider == "insightface_buffalo_l":
            return "insightface_buffalo_l"
        return "mock_face_recognizer"

    def _decode_and_validate(self, payload: Any, max_image_mb: float, timings: dict[str, float]) -> bytes:
        decode_start = time.perf_counter()
        decoded = self.decoder.decode(payload.data, payload.kind)
        timings["decode"] += round((time.perf_counter() - decode_start) * 1000.0, 2)
        size_mb = len(decoded) / (1024 * 1024)
        if size_mb > max_image_mb:
            raise InvalidImagePayloadError(f"image exceeds {max_image_mb}MB")
        return decoded

    def _decode_image_bytes(self, image_bytes: bytes) -> np.ndarray:
        return self.decoder.decode_image_to_array(image_bytes)

    def _validate_quality(self, detections: list[FaceDetectionSchema], policy: Any, which: str) -> None:
        if not detections:
            if policy.reject_if_no_face:
                raise FaceQualityError("no_face_detected", f"no face detected in {which}")
            return
        if len(detections) > 1 and policy.reject_if_multiple_faces:
            raise FaceQualityError("multiple_faces_detected", f"multiple faces detected in {which}")
        if any(detection.detection_confidence < policy.min_detection_confidence for detection in detections):
            raise FaceQualityError("face_quality_rejected", f"face quality rejected for {which}")
