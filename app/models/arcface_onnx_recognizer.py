from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.errors import ArcFaceInferenceError, ArcFaceModelNotFoundError, InvalidEmbeddingShapeError
from app.services.recognizer_base import BaseFaceRecognizer

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None


class ArcFaceOnnxRecognizer(BaseFaceRecognizer):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = None
        self.input_name = None
        self.output_name = None
        self._load_session()

    def _load_session(self) -> None:
        if not Path(self.settings.arcface_model_path).exists():
            raise ArcFaceModelNotFoundError(
                "ArcFace ONNX model not found. Please place face-recognition-resnet100-arcface.onnx inside the models/ directory."
            )
        if ort is None:
            raise ArcFaceInferenceError("onnxruntime is not installed")

        self.session = ort.InferenceSession(self.settings.arcface_model_path, providers=self.providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if self.session is None:
            self._load_session()

        image = np.asarray(aligned_face, dtype=np.uint8)
        if image.ndim != 3 or image.shape[0:2] != (self.settings.arcface_input_size, self.settings.arcface_input_size):
            raise InvalidEmbeddingShapeError("invalid input shape for ArcFace embedding")

        model_input = self._preprocess(image)

        try:
            outputs = self.session.run([self.output_name], {self.input_name: model_input})[0]
        except Exception as exc:
            raise ArcFaceInferenceError("arcface inference failed") from exc

        embedding = np.asarray(outputs, dtype=np.float32).reshape(-1)
        if embedding.shape[0] != self.settings.arcface_embedding_dim:
            raise InvalidEmbeddingShapeError("invalid embedding shape")

        norm = np.linalg.norm(embedding)
        return embedding if norm == 0.0 else embedding / norm

    def _preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        normalization = self.settings.arcface_normalization
        if normalization not in {"raw_0_255", "raw_rgb_0_255", "minus127_5_div128"}:
            raise ArcFaceInferenceError(f"unsupported ArcFace normalization: {normalization}")

        image = image_bgr[:, :, ::-1] if normalization != "raw_0_255" else image_bgr
        image = image.astype(np.float32)
        if normalization == "minus127_5_div128":
            image = (image - 127.5) / 128.0
        return np.expand_dims(np.transpose(image, (2, 0, 1)), axis=0)

    @property
    def providers(self) -> list[str]:
        return [provider.strip() for provider in self.settings.onnx_providers.split(",") if provider.strip()]

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "arcface_r100_onnx",
            "path": self.settings.arcface_model_path,
            "input_name": self.input_name,
            "output_name": self.output_name,
            "providers": self.providers,
            "embedding_dim": self.settings.arcface_embedding_dim,
            "normalization": self.settings.arcface_normalization,
        }
