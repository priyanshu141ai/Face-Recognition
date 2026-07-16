from pathlib import Path
import hashlib
from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.errors import ArcFaceInferenceError, ArcFaceModelNotFoundError, InvalidEmbeddingShapeError
from app.services.recognizer_base import BaseFaceRecognizer

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None


class ArcFaceOnnxRecognizer(BaseFaceRecognizer):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
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
        with open(self.settings.arcface_model_path, "rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if self.settings.arcface_sha256 and digest != self.settings.arcface_sha256:
            raise ArcFaceInferenceError("ArcFace model checksum does not match the pinned artifact")
        if digest == self.settings.arcface_sha256 and self.settings.arcface_normalization != "raw_rgb_0_255":
            raise ArcFaceInferenceError("pinned ArcFace model requires raw_rgb_0_255 preprocessing")
        self.sha256 = digest

        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = self.settings.ort_intra_op_threads
        session_options.inter_op_num_threads = self.settings.ort_inter_op_threads
        self.session = ort.InferenceSession(
            self.settings.arcface_model_path,
            sess_options=session_options,
            providers=self.providers,
        )
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
            "sha256": self.sha256,
            "license_note": "ONNX Model Zoo ArcFace weights; verify deployment license",
        }
