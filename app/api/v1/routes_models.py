from fastapi import APIRouter

router = APIRouter(prefix="/v1/models", tags=["models"])


@router.get("/current")
def current_models() -> dict[str, str]:
    return {
        "detector": "mock_yunet_adapter_v1",
        "recognizer": "mock_arcface_adapter_v1",
        "preprocessing": "align112_rgb_mock_v1",
        "threshold": "0.40",
        "calibration": "linear_mock_v1",
    }
