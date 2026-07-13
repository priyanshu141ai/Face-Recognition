from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import abuse_service, repository_dependency
from app.core.config import get_settings
from app.core.errors import ArcFaceInferenceError, ArcFaceModelNotFoundError, CalibrationProfileError, DetectorProviderError, FaceAlignmentError, FaceQualityError, InvalidEmbeddingShapeError, InvalidImagePayloadError, RecognizerProviderError
from app.core.gateway_security import gateway_action, require_body_binding
from app.core.security import require_bearer_token
from app.schemas.gateway import GatewayAssertionClaims
from app.schemas.face import DetectRequest, EmbedRequest, VerifyRequest, VerifyResponse
from app.services.image_decoder import ImageDecoder
from app.services.pipeline import get_face_verification_pipeline

router = APIRouter(prefix="/v1/faces", tags=["faces"])

VERIFY_ERROR_MAP = {
    ArcFaceModelNotFoundError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "arcface_model_not_found"),
    ArcFaceInferenceError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "arcface_inference_failed"),
    InvalidEmbeddingShapeError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "invalid_embedding_shape"),
    FaceAlignmentError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "face_alignment_failed"),
    RecognizerProviderError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "recognizer_provider_invalid"),
    DetectorProviderError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "detector_provider_invalid"),
    CalibrationProfileError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "calibration_profile_invalid"),
}


def _api_error(status_code: int, request_id: str | None, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"request_id": request_id, "error": {"code": code, "message": message}})


def _rate_limit(request: Request, action: str) -> None:
    settings = get_settings()
    repository = repository_dependency()
    abuse_service(repository).check(
        request, action, limit=settings.low_level_face_limit_per_minute, window_seconds=60
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_face(
    request: VerifyRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_engine_verify")),
) -> dict[str, object]:
    require_body_binding(gateway, request_id=request.request_id)
    settings = get_settings()
    _rate_limit(http_request, "face_engine_verify")
    try:
        pipeline = get_face_verification_pipeline()
        return pipeline.verify(request, settings.max_image_mb)
    except tuple(VERIFY_ERROR_MAP) as exc:
        status_code, code = VERIFY_ERROR_MAP[type(exc)]
        raise _api_error(status_code, request.request_id, code, exc.message) from exc
    except FaceQualityError as exc:
        raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, request.request_id, exc.code, exc.message) from exc
    except InvalidImagePayloadError as exc:
        raise _api_error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, request.request_id, "invalid_image_payload", exc.message) from exc


@router.post("/detect")
def detect_faces(
    request: DetectRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_engine_detect")),
) -> dict[str, object]:
    require_body_binding(gateway, request_id=request.request_id)
    settings = get_settings()
    _rate_limit(http_request, "face_engine_detect")
    try:
        decoder = ImageDecoder(settings.max_image_pixels)
        image_bytes = decoder.decode(
            request.image.data, request.image.kind, int(settings.max_image_mb * 1024 * 1024)
        )
        if len(image_bytes) / (1024 * 1024) > settings.max_image_mb:
            raise InvalidImagePayloadError(f"image exceeds {settings.max_image_mb}MB")
        pipeline = get_face_verification_pipeline()
        with pipeline.inference_lock:
            faces = pipeline._get_detector().detect(image_bytes, None)
            pipeline._validate_quality(faces, request.quality_policy, "image")
        return {"request_id": request.request_id, "faces": [face.model_dump() for face in faces]}
    except FaceQualityError as exc:
        raise _api_error(422, request.request_id, exc.code, exc.message) from exc
    except InvalidImagePayloadError as exc:
        raise _api_error(415, request.request_id, "invalid_image_payload", exc.message) from exc
    except DetectorProviderError as exc:
        raise _api_error(500, request.request_id, "detector_provider_invalid", exc.message) from exc


@router.post("/embed")
def embed_faces(
    request: EmbedRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_engine_embed")),
) -> dict[str, object]:
    require_body_binding(gateway, request_id=request.request_id)
    settings = get_settings()
    _rate_limit(http_request, "face_engine_embed")
    try:
        pipeline = get_face_verification_pipeline()
        with pipeline.inference_lock:
            image_bytes = ImageDecoder(settings.max_image_pixels).decode(
                request.image.data, request.image.kind, int(settings.max_image_mb * 1024 * 1024)
            )
            if len(image_bytes) / (1024 * 1024) > settings.max_image_mb:
                raise InvalidImagePayloadError(f"image exceeds {settings.max_image_mb}MB")
            faces = pipeline._get_detector().detect(image_bytes, None)
            pipeline._validate_quality(faces, request.quality_policy, "image")
            selected = pipeline._select_faces(faces, request.face_selector, request.face_index)
            aligned = pipeline.preprocessor.align_face(pipeline._decode_image_bytes(image_bytes), selected[0])
            embedding = pipeline._get_recognizer().embed(aligned)
        return {
            "request_id": request.request_id,
            "embedding": embedding.tolist() if request.return_embeddings and settings.allow_embedding_return else None,
            "embedding_returned": bool(request.return_embeddings and settings.allow_embedding_return),
        }
    except FaceQualityError as exc:
        raise _api_error(422, request.request_id, exc.code, exc.message) from exc
    except InvalidImagePayloadError as exc:
        raise _api_error(415, request.request_id, "invalid_image_payload", exc.message) from exc
    except Exception as exc:
        raise _api_error(500, request.request_id, "embedding_failed", "Face embedding failed") from exc
