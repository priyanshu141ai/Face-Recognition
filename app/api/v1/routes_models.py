from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import require_bearer_token
from app.services.calibration import resolve_match_policy

router = APIRouter(prefix="/v1/models", tags=["models"])


@router.get("/current")
def current_models(_: None = Depends(require_bearer_token)) -> dict[str, object]:
    settings = get_settings()
    calibrator, threshold = resolve_match_policy(settings)
    detector_names = {
        "mock": "mock_yunet_adapter_v1",
        "yunet": "yunet_2023mar_opencv",
    }
    detector_paths = {
        "mock": None,
        "yunet": settings.yunet_model_path,
    }
    recognizer_names = {
        "mock": "mock_arcface_adapter_v1",
        "arcface_onnx": "arcface_r100_onnx",
        "mobilefacenet_onnx": "mobilefacenet_onnx",
        "insightface_buffalo_l": "insightface_buffalo_l",
    }
    recognizer_paths = {
        "mock": None,
        "arcface_onnx": settings.arcface_model_path,
        "mobilefacenet_onnx": settings.mobilefacenet_model_path,
        "insightface_buffalo_l": settings.insightface_model_name,
    }
    recognizer_dims = {
        "mock": 16,
        "arcface_onnx": settings.arcface_embedding_dim,
        "mobilefacenet_onnx": settings.mobilefacenet_embedding_dim,
        "insightface_buffalo_l": 512,
    }
    return {
        "detector": {
            "name": detector_names.get(settings.detector_provider, settings.detector_provider),
            "path": detector_paths.get(settings.detector_provider),
            "score_threshold": settings.yunet_score_threshold,
        },
        "recognizer": {
            "name": recognizer_names.get(settings.recognizer_provider, settings.recognizer_provider),
            "path": recognizer_paths.get(settings.recognizer_provider),
            "embedding_dim": recognizer_dims.get(settings.recognizer_provider),
            "input_size": settings.arcface_input_size,
            "providers": [provider.strip() for provider in settings.onnx_providers.split(",") if provider.strip()],
        },
        "preprocessing": {
            "name": "align112_rgb_v1",
            "input_size": 112,
            "normalization": settings.arcface_normalization,
        },
        "threshold": {
            "score_type": "cosine",
            "value": threshold,
            "operating_point": calibrator.operating_point,
        },
        "calibration": {
            **calibrator.metadata(),
        },
    }
