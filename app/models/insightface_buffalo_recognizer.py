from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.services.recognizer_base import BaseFaceRecognizer


class InsightFaceBuffaloRecognizer(BaseFaceRecognizer):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            insightface = importlib.import_module("insightface")
        except ImportError as exc:
            raise RuntimeError("InsightFace is not installed. Install optional benchmark dependencies before using buffalo_l.") from exc
        try:
            app = insightface.app.FaceAnalysis(
                name=self.settings.insightface_model_name,
                root=str(Path.home() / ".insightface"),
                allowed_modules=["recognition"],
                providers=[p.strip() for p in self.settings.onnx_providers.split(",") if p.strip()],
            )
            app.prepare(ctx_id=self.settings.insightface_ctx_id)
            self._model = app.models["recognition"]
        except Exception as exc:
            raise RuntimeError(f"InsightFace {self.settings.insightface_model_name} recognition model is not ready") from exc

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("InsightFace model is not ready")
        embedding = np.asarray(self._model.get_feat(np.asarray(aligned_face, dtype=np.uint8)), dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(embedding)
        return embedding if norm == 0.0 else embedding / norm

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "insightface_buffalo_l",
            "version": self.settings.insightface_model_name,
            "provider": "insightface_buffalo_l",
            "embedding_dim": 512,
            "input_size": self.settings.arcface_input_size,
            "preprocess_version": "insightface_get_feat_v1",
            "model_path": str(Path.home() / ".insightface" / "models" / self.settings.insightface_model_name),
            "license_note": "InsightFace pretrained weights: non-commercial research only",
        }
