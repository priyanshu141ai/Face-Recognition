from __future__ import annotations

import os
import hashlib
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
        self.sha256 = None
        self._load_session()

    def _load_session(self) -> None:
        model_path = self.settings.mobilefacenet_model_path
        if not os.path.exists(model_path):
            raise FileNotFoundError("MobileFaceNet ONNX model not found")
        with open(model_path, "rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if self.settings.mobilefacenet_sha256 and digest != self.settings.mobilefacenet_sha256:
            raise RuntimeError("MobileFaceNet model checksum does not match the pinned buffalo_sc artifact")
        self.sha256 = digest
        if ort is None:
            raise RuntimeError("onnxruntime is not installed")
        providers = [provider.strip() for provider in self.settings.onnx_providers.split(",") if provider.strip()]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        output_shape = self.session.get_outputs()[0].shape
        if list(input_shape[-3:]) != [3, 112, 112] or output_shape[-1] != self.settings.mobilefacenet_embedding_dim:
            raise RuntimeError("MobileFaceNet ONNX input/output contract is incompatible")

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if self.session is None:
            self._load_session()
        image = np.asarray(aligned_face, dtype=np.uint8)
        if image.shape != (self.settings.mobilefacenet_input_size, self.settings.mobilefacenet_input_size, 3):
            raise RuntimeError("MobileFaceNet input must be 112x112 BGR")
        image = self._preprocess(image)
        outputs = self.session.run([self.output_name], {self.input_name: image})[0]
        embedding = np.asarray(outputs, dtype=np.float32).reshape(-1)
        if embedding.shape[0] != self.settings.mobilefacenet_embedding_dim:
            raise RuntimeError("MobileFaceNet embedding dimension is incompatible")
        norm = np.linalg.norm(embedding)
        if norm == 0.0:
            return embedding
        return embedding / norm

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        image = image[:, :, ::-1].astype(np.float32)
        image = (image - 127.5) / 127.5
        image = np.transpose(image, (2, 0, 1))
        return np.expand_dims(image, axis=0)

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
            "sha256": self.sha256,
            "providers": [provider.strip() for provider in self.settings.onnx_providers.split(",") if provider.strip()],
            "license_note": "InsightFace buffalo_sc weights: non-commercial research only",
        }
