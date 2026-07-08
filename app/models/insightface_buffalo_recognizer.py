from __future__ import annotations

import importlib
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
            importlib.import_module("insightface")
        except ImportError as exc:
            raise RuntimeError("InsightFace is not installed. Install optional benchmark dependencies before using buffalo_l.") from exc

        if not self.settings.arcface_model_path:
            raise RuntimeError("InsightFace model pack is missing")

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("InsightFace model is not ready")
        return np.asarray(np.zeros(512, dtype=np.float32))

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "insightface_buffalo_l",
            "version": "optional",
            "provider": "insightface_buffalo_l",
            "embedding_dim": 512,
            "input_size": self.settings.arcface_input_size,
            "preprocess_version": "buffalo_l_optional",
            "model_path": self.settings.arcface_model_path,
            "license_note": "optional benchmark dependency",
        }
