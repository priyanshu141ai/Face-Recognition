import time
from pathlib import Path
from typing import Any

import numpy as np

from app.benchmark.dataset import load_benchmark_pairs
from app.core.config import get_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.services.alignment import FaceAligner
from app.services.image_decoder import ImageDecoder
from app.services.matcher import FaceMatcher


class BenchmarkRunner:
    def __init__(self, models: list[str], dataset_path: str | Path, threshold: float | None = None) -> None:
        self.settings = get_settings()
        self.models = models
        self.dataset_path = Path(dataset_path)
        self.threshold = threshold if threshold is not None else self.settings.match_threshold
        self.decoder = ImageDecoder()
        self.aligner = FaceAligner()
        self.face_matcher = FaceMatcher(threshold=self.threshold)
        self.detector = YuNetFaceDetector() if self.settings.detector_provider == "yunet" else MockFaceDetector()

    def run(self) -> list[dict[str, Any]]:
        pairs = load_benchmark_pairs(self.dataset_path)
        results: list[dict[str, Any]] = []
        for model_name in self.models:
            recognizer = self._build_recognizer(model_name)
            metadata = getattr(recognizer, "metadata", {}) or {}
            for pair in pairs:
                result = self._evaluate_pair(model_name, pair, recognizer, metadata)
                results.append(result)
        return results

    def _evaluate_pair(self, model_name: str, pair: Any, recognizer: Any, metadata: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        error_code = None
        error_message = None
        try:
            decode_start = time.perf_counter()
            image_a_bytes = Path(pair.image_a_path).read_bytes()
            image_b_bytes = Path(pair.image_b_path).read_bytes()
            image_a = self.decoder.decode_image_to_array(image_a_bytes)
            image_b = self.decoder.decode_image_to_array(image_b_bytes)
            decode_ms = round((time.perf_counter() - decode_start) * 1000.0, 2)

            detect_start = time.perf_counter()
            detections_a = self._select_faces(self.detector.detect(image_a_bytes, None))
            detections_b = self._select_faces(self.detector.detect(image_b_bytes, None))
            detect_ms = round((time.perf_counter() - detect_start) * 1000.0, 2)
            if not detections_a or not detections_b:
                raise FaceQualityError("no_face_detected", "no face detected")

            align_start = time.perf_counter()
            aligned_a = self.aligner.align_face_112(image_a, detections_a[0].landmarks5)
            aligned_b = self.aligner.align_face_112(image_b, detections_b[0].landmarks5)
            align_ms = round((time.perf_counter() - align_start) * 1000.0, 2)

            embed_start = time.perf_counter()
            emb_a = recognizer.embed(aligned_a)
            emb_b = recognizer.embed(aligned_b)
            embed_ms = round((time.perf_counter() - embed_start) * 1000.0, 2)

            match_start = time.perf_counter()
            similarity = self.face_matcher.cosine_similarity(emb_a, emb_b)
            match_ms = round((time.perf_counter() - match_start) * 1000.0, 2)
            decision = self.face_matcher.decide(similarity)
            return {
                "model_name": model_name,
                "image_a": pair.image_a_path,
                "image_b": pair.image_b_path,
                "label": pair.label,
                "similarity_cosine": round(float(similarity), 6),
                "prediction": decision,
                "threshold": self.threshold,
                "decode_ms": decode_ms,
                "detect_ms": detect_ms,
                "align_ms": align_ms,
                "embed_ms": embed_ms,
                "match_ms": match_ms,
                "total_ms": round((time.perf_counter() - start) * 1000.0, 2),
                "embedding_dim": int(np.asarray(emb_a).shape[0]),
                "embedding_l2_norm_a": round(float(np.linalg.norm(emb_a)), 6),
                "embedding_l2_norm_b": round(float(np.linalg.norm(emb_b)), 6),
                "detector_used": "yunet_2023mar_opencv" if self.settings.detector_provider == "yunet" else "mock_yunet_adapter_v1",
                "alignment_used": "5-point similarity transform to 112x112",
                "recognizer_used": metadata.get("name", model_name),
                "preprocessing_version": metadata.get("preprocess_version", "align112_rgb_v1"),
                "license_note": metadata.get("license_note", "weights may have separate licenses"),
                "error_code": None,
                "error_message": None,
            }
        except Exception as exc:  # pragma: no cover - benchmark robustness
            error_code = getattr(exc, "code", exc.__class__.__name__)
            error_message = str(exc)
            return {
                "model_name": model_name,
                "image_a": pair.image_a_path,
                "image_b": pair.image_b_path,
                "label": pair.label,
                "similarity_cosine": None,
                "prediction": "non_match",
                "threshold": self.threshold,
                "decode_ms": 0.0,
                "detect_ms": 0.0,
                "align_ms": 0.0,
                "embed_ms": 0.0,
                "match_ms": 0.0,
                "total_ms": round((time.perf_counter() - start) * 1000.0, 2),
                "embedding_dim": metadata.get("embedding_dim"),
                "embedding_l2_norm_a": None,
                "embedding_l2_norm_b": None,
                "detector_used": "yunet_2023mar_opencv" if self.settings.detector_provider == "yunet" else "mock_yunet_adapter_v1",
                "alignment_used": "5-point similarity transform to 112x112",
                "recognizer_used": metadata.get("name", model_name),
                "preprocessing_version": metadata.get("preprocess_version", "align112_rgb_v1"),
                "license_note": metadata.get("license_note", "weights may have separate licenses"),
                "error_code": error_code,
                "error_message": error_message,
            }

    def _build_recognizer(self, provider: str) -> Any:
        if provider == "mock":
            return MockFaceRecognizer()
        if provider == "arcface_onnx":
            return ArcFaceOnnxRecognizer()
        if provider == "mobilefacenet_onnx":
            from app.models.mobilefacenet_onnx_recognizer import MobileFaceNetOnnxRecognizer
            return MobileFaceNetOnnxRecognizer()
        if provider == "insightface_buffalo_l":
            from app.models.insightface_buffalo_recognizer import InsightFaceBuffaloRecognizer
            return InsightFaceBuffaloRecognizer()
        raise ValueError(f"unsupported provider {provider}")

    def _select_faces(self, detections: list[Any]) -> list[Any]:
        return [max(detections, key=lambda item: item.detection_confidence)] if detections else []
