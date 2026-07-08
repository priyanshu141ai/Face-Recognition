import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_bearer_token: str | None = None
    max_image_mb: float = 5.0
    log_level: str = "INFO"
    provider: str = "mock"
    version: str = "phase-4.1"
    detector_provider: str = "mock"
    recognizer_provider: str = "mock"
    yunet_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    yunet_score_threshold: float = 0.85
    yunet_nms_threshold: float = 0.3
    yunet_top_k: int = 5000
    min_face_size: int = 20
    max_image_dimension: int = 640
    arcface_model_path: str = "models/face-recognition-resnet100-arcface.onnx"
    mobilefacenet_model_path: str = "models/mobilefacenet.onnx"
    mobilefacenet_input_size: int = 112
    mobilefacenet_embedding_dim: int = 512
    insightface_model_name: str = "buffalo_l"
    insightface_det_size: int = 640
    insightface_ctx_id: int = -1
    arcface_input_size: int = 112
    arcface_embedding_dim: int = 512
    arcface_normalization: str = "raw_0_255"
    arcface_use_gpu: bool = False
    onnx_providers: str = "CPUExecutionProvider"
    match_threshold: float = 0.40
    return_embeddings_default: bool = False
    allow_embedding_return: bool = False
    benchmark_output_dir: str = "benchmark_reports"
    benchmark_target_fmr_values: str = "1e-3,1e-4,1e-5"
    benchmark_default_models: str = "arcface_onnx,mobilefacenet_onnx"
    benchmark_save_per_pair: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_bearer_token=os.getenv("API_BEARER_TOKEN") or None,
            max_image_mb=float(os.getenv("MAX_IMAGE_MB", "5.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            provider=os.getenv("MODEL_PROVIDER", "mock"),
            version=os.getenv("BACKEND_VERSION", "phase-4.1"),
            detector_provider=os.getenv("DETECTOR_PROVIDER", "mock"),
            recognizer_provider=os.getenv("RECOGNIZER_PROVIDER", "mock"),
            yunet_model_path=os.getenv("YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx"),
            yunet_score_threshold=float(os.getenv("YUNET_SCORE_THRESHOLD", "0.85")),
            yunet_nms_threshold=float(os.getenv("YUNET_NMS_THRESHOLD", "0.3")),
            yunet_top_k=int(os.getenv("YUNET_TOP_K", "5000")),
            min_face_size=int(os.getenv("MIN_FACE_SIZE", "20")),
            max_image_dimension=int(os.getenv("MAX_IMAGE_DIMENSION", "640")),
            arcface_model_path=os.getenv("ARCFACE_MODEL_PATH", "models/face-recognition-resnet100-arcface.onnx"),
            mobilefacenet_model_path=os.getenv("MOBILEFACENET_MODEL_PATH", "models/mobilefacenet.onnx"),
            mobilefacenet_input_size=int(os.getenv("MOBILEFACENET_INPUT_SIZE", "112")),
            mobilefacenet_embedding_dim=int(os.getenv("MOBILEFACENET_EMBEDDING_DIM", "512")),
            insightface_model_name=os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l"),
            insightface_det_size=int(os.getenv("INSIGHTFACE_DET_SIZE", "640")),
            insightface_ctx_id=int(os.getenv("INSIGHTFACE_CTX_ID", "-1")),
            arcface_input_size=int(os.getenv("ARCFACE_INPUT_SIZE", "112")),
            arcface_embedding_dim=int(os.getenv("ARCFACE_EMBEDDING_DIM", "512")),
            arcface_normalization=os.getenv("ARCFACE_NORMALIZATION", "raw_0_255"),
            arcface_use_gpu=os.getenv("ARCFACE_USE_GPU", "false").lower() == "true",
            onnx_providers=os.getenv("ONNX_PROVIDERS", "CPUExecutionProvider"),
            match_threshold=float(os.getenv("MATCH_THRESHOLD", "0.40")),
            return_embeddings_default=os.getenv("RETURN_EMBEDDINGS_DEFAULT", "false").lower() == "true",
            allow_embedding_return=os.getenv("ALLOW_EMBEDDING_RETURN", "false").lower() == "true",
            benchmark_output_dir=os.getenv("BENCHMARK_OUTPUT_DIR", "benchmark_reports"),
            benchmark_target_fmr_values=os.getenv("BENCHMARK_TARGET_FMR_VALUES", "1e-3,1e-4,1e-5"),
            benchmark_default_models=os.getenv("BENCHMARK_DEFAULT_MODELS", "arcface_onnx,mobilefacenet_onnx"),
            benchmark_save_per_pair=os.getenv("BENCHMARK_SAVE_PER_PAIR", "true").lower() == "true",
        )


def get_settings() -> Settings:
    return Settings.from_env()
