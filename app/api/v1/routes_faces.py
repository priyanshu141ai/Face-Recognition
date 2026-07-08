from fastapi import APIRouter, Depends, HTTPException, status
import numpy as np

from app.core.config import get_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.security import require_bearer_token
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.schemas.face import VerifyRequest, VerifyResponse
from app.services.pipeline import FaceVerificationPipeline

router = APIRouter(prefix="/v1/faces", tags=["faces"])


@router.post("/verify", response_model=VerifyResponse)
def verify_face(request: VerifyRequest, _: None = Depends(require_bearer_token)) -> dict[str, object]:
    settings = get_settings()
    pipeline = FaceVerificationPipeline()
    try:
        return pipeline.verify(request, settings.max_image_mb)
    except FaceQualityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error_code": exc.code, "message": exc.message}) from exc
    except InvalidImagePayloadError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"error_code": "invalid_image_payload", "message": exc.message}) from exc


@router.post("/detect")
def detect_faces() -> dict[str, object]:
    detector = MockFaceDetector()
    return {"faces": [detection.model_dump() for detection in detector.detect(b"mock-image")]}


@router.post("/embed")
def embed_faces(return_embeddings: bool = False) -> dict[str, object]:
    recognizer = MockFaceRecognizer()
    embedding = None
    if return_embeddings:
        embedding = recognizer.embed(np.zeros((112, 112, 3), dtype=np.uint8)).tolist()
    return {"embedding": embedding}
