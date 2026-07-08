from __future__ import annotations

import os
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.services.recognizer_base import BaseFaceRecognizer

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None


class MobileFaceNetOnnxRecognizer(BaseFaceRecognizer):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = None
        self.input_name = None
        self.output_name = None
        self._load_session()

    def _load_session(self) -> None:
        model_path = self.settings.mobilefacenet_model_path
        if not os.path.exists(model_path):
            raise FileNotFoundError("MobileFaceNet ONNX model not found")
        if ort is None:
            raise RuntimeError("onnxruntime is not installed")
        providers = [provider.strip() for provider in self.settings.onnx_providers.split(",") if provider.strip()]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if self.session is None:
            self._load_session()
        image = np.asarray(aligned_face, dtype=np.uint8)
        image = image[:, :, ::-1].astype(np.float32)
        image = (image - 127.5) / 128.0
        image = np.transpose(image, (2, 0, 1))
        image = np.expand_dims(image, axis=0)
        outputs = self.session.run([self.output_name], {self.input_name: image})[0]
        embedding = np.asarray(outputs, dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(embedding)
        if norm == 0.0:
            return embedding
        return embedding / norm

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "mobilefacenet_onnx",
            "version": "onnx",
            "provider": "mobilefacenet_onnx",
            "embedding_dim": self.settings.mobilefacenet_embedding_dim,
            "input_size": self.settings.mobilefacenet_input_size,
            "preprocess_version": "mobilefacenet_v1",
            "model_path": self.settings.mobilefacenet_model_path,
            "license_note": "benchmark optional",
        }
