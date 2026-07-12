import time
import hashlib
import platform
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
    def __init__(self, models: list[str], dataset_path: str | Path, threshold: float | None = None, detector_provider: str = "yunet", allow_mock: bool = False) -> None:
        self.settings = get_settings()
        self.models = models
        self.dataset_path = Path(dataset_path)
        self.threshold = threshold if threshold is not None else self.settings.match_threshold
        self.decoder = ImageDecoder()
        self.aligner = FaceAligner()
        self.face_matcher = FaceMatcher(threshold=self.threshold)
        if detector_provider == "mock" and not allow_mock:
            raise ValueError("mock detector requires explicit allow_mock=True")
        if detector_provider not in {"yunet", "mock"}:
            raise ValueError(f"unsupported detector {detector_provider}")
        self.dataset_sha256 = hashlib.sha256((self.dataset_path / "pairs.csv").read_bytes()).hexdigest()
        self.detector_provider = detector_provider
        self.detector = YuNetFaceDetector() if detector_provider == "yunet" else MockFaceDetector()
        self._feature_cache: dict[str, tuple[np.ndarray, dict[str, float]]] = {}
        self._feature_errors: dict[str, Exception] = {}

    def run(self) -> list[dict[str, Any]]:
        pairs = load_benchmark_pairs(self.dataset_path)
        results: list[dict[str, Any]] = []
        for model_name in self.models:
            recognizer = self._build_recognizer(model_name)
            self._feature_cache.clear()
            self._feature_errors.clear()
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
            emb_a, timings_a, cached_a = self._feature(pair.image_a_path, recognizer)
            emb_b, timings_b, cached_b = self._feature(pair.image_b_path, recognizer)
            decode_ms = timings_a["decode_ms"] + timings_b["decode_ms"]
            detect_ms = timings_a["detect_ms"] + timings_b["detect_ms"]
            align_ms = timings_a["align_ms"] + timings_b["align_ms"]
            embed_ms = timings_a["embed_ms"] + timings_b["embed_ms"]
            uncached_images = int(not cached_a) + int(not cached_b)
            image_pipeline_ms = (decode_ms + detect_ms + align_ms + embed_ms) / uncached_images if uncached_images else None

            match_start = time.perf_counter()
            similarity = self.face_matcher.cosine_similarity(emb_a, emb_b)
            match_ms = round((time.perf_counter() - match_start) * 1000.0, 2)
            decision = self.face_matcher.decide(similarity)
            return {
                "model_name": model_name,
                "image_a": pair.image_a_path,
                "image_b": pair.image_b_path,
                "label": pair.label,
                "split": pair.split,
                "subject_a": pair.subject_a,
                "subject_b": pair.subject_b,
                "fold_a": pair.fold_a,
                "fold_b": pair.fold_b,
                "similarity_cosine": round(float(similarity), 6),
                "prediction": decision,
                "threshold": self.threshold,
                "decode_ms": decode_ms,
                "detect_ms": detect_ms,
                "align_ms": align_ms,
                "embed_ms": embed_ms,
                "match_ms": match_ms,
                "total_ms": round((time.perf_counter() - start) * 1000.0, 2),
                "image_pipeline_ms": round(image_pipeline_ms, 2) if image_pipeline_ms is not None else None,
                "uncached_images": uncached_images,
                "embedding_dim": int(np.asarray(emb_a).shape[0]),
                "embedding_l2_norm_a": round(float(np.linalg.norm(emb_a)), 6),
                "embedding_l2_norm_b": round(float(np.linalg.norm(emb_b)), 6),
                "detector_used": "yunet_2023mar_opencv" if self.detector_provider == "yunet" else "mock_yunet_adapter_v1",
                "alignment_used": "5-point similarity transform to 112x112",
                "recognizer_used": metadata.get("name", model_name),
                "preprocessing_version": metadata.get("preprocess_version", "align112_rgb_v1"),
                "license_note": metadata.get("license_note", "weights may have separate licenses"),
                "model_sha256": metadata.get("sha256"),
                "dataset_sha256": self.dataset_sha256,
                "runtime_providers": metadata.get("providers", self.settings.onnx_providers),
                "runtime_platform": platform.platform(),
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
                "split": pair.split,
                "subject_a": pair.subject_a,
                "subject_b": pair.subject_b,
                "fold_a": pair.fold_a,
                "fold_b": pair.fold_b,
                "similarity_cosine": None,
                "prediction": "non_match",
                "threshold": self.threshold,
                "decode_ms": 0.0,
                "detect_ms": 0.0,
                "align_ms": 0.0,
                "embed_ms": 0.0,
                "match_ms": 0.0,
                "total_ms": round((time.perf_counter() - start) * 1000.0, 2),
                "image_pipeline_ms": None,
                "uncached_images": 0,
                "embedding_dim": metadata.get("embedding_dim"),
                "embedding_l2_norm_a": None,
                "embedding_l2_norm_b": None,
                "detector_used": "yunet_2023mar_opencv" if self.detector_provider == "yunet" else "mock_yunet_adapter_v1",
                "alignment_used": "5-point similarity transform to 112x112",
                "recognizer_used": metadata.get("name", model_name),
                "preprocessing_version": metadata.get("preprocess_version", "align112_rgb_v1"),
                "license_note": metadata.get("license_note", "weights may have separate licenses"),
                "model_sha256": metadata.get("sha256"),
                "dataset_sha256": self.dataset_sha256,
                "runtime_providers": metadata.get("providers", self.settings.onnx_providers),
                "runtime_platform": platform.platform(),
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

    def _feature(self, image_path: str, recognizer: Any) -> tuple[np.ndarray, dict[str, float], bool]:
        if image_path in self._feature_errors:
            raise self._feature_errors[image_path]
        if image_path in self._feature_cache:
            embedding, _ = self._feature_cache[image_path]
            return embedding, {key: 0.0 for key in ("decode_ms", "detect_ms", "align_ms", "embed_ms")}, True
        try:
            started = time.perf_counter()
            image_bytes = Path(image_path).read_bytes()
            image = self.decoder.decode_image_to_array(image_bytes)
            decode_ms = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            detections = self._select_faces(self.detector.detect(image_bytes, None))
            detect_ms = (time.perf_counter() - started) * 1000.0
            if not detections:
                raise FaceQualityError("no_face_detected", "no face detected")
            started = time.perf_counter()
            aligned = self.aligner.align_face_112(image, detections[0].landmarks5)
            align_ms = (time.perf_counter() - started) * 1000.0
            started = time.perf_counter()
            embedding = recognizer.embed(aligned)
            embed_ms = (time.perf_counter() - started) * 1000.0
        except Exception as exc:
            self._feature_errors[image_path] = exc
            raise
        timings = {key: round(value, 2) for key, value in {
            "decode_ms": decode_ms, "detect_ms": detect_ms, "align_ms": align_ms, "embed_ms": embed_ms,
        }.items()}
        self._feature_cache[image_path] = (embedding, timings)
        return embedding, timings, False

    def _select_faces(self, detections: list[Any]) -> list[Any]:
        return [max(detections, key=lambda item: item.detection_confidence)] if detections else []
