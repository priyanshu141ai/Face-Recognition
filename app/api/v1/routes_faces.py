from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.errors import ArcFaceInferenceError, ArcFaceModelNotFoundError, DetectorProviderError, FaceAlignmentError, FaceQualityError, InvalidEmbeddingShapeError, InvalidImagePayloadError, RecognizerProviderError
from app.core.security import require_bearer_token
from app.schemas.face import DetectRequest, EmbedRequest, VerifyRequest, VerifyResponse
from app.services.image_decoder import ImageDecoder
from app.services.pipeline import FaceVerificationPipeline

router = APIRouter(prefix="/v1/faces", tags=["faces"])


@router.post("/verify", response_model=VerifyResponse)
def verify_face(request: VerifyRequest, _: None = Depends(require_bearer_token)) -> dict[str, object]:
    settings = get_settings()
    pipeline = FaceVerificationPipeline()
    try:
        return pipeline.verify(request, settings.max_image_mb)
    except ArcFaceModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "arcface_model_not_found", "message": exc.message}}) from exc
    except ArcFaceInferenceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "arcface_inference_failed", "message": exc.message}}) from exc
    except InvalidEmbeddingShapeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "invalid_embedding_shape", "message": exc.message}}) from exc
    except FaceAlignmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "face_alignment_failed", "message": exc.message}}) from exc
    except RecognizerProviderError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "recognizer_provider_invalid", "message": exc.message}}) from exc
    except DetectorProviderError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"request_id": request.request_id, "error": {"code": "detector_provider_invalid", "message": exc.message}}) from exc
    except FaceQualityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"request_id": request.request_id, "error": {"code": exc.code, "message": exc.message}}) from exc
    except InvalidImagePayloadError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"request_id": request.request_id, "error": {"code": "invalid_image_payload", "message": exc.message}}) from exc


@router.post("/detect")
def detect_faces(request: DetectRequest, _: None = Depends(require_bearer_token)) -> dict[str, object]:
    settings = get_settings()
    try:
        decoder = ImageDecoder()
        image_bytes = decoder.decode(request.image.data, request.image.kind)
        if len(image_bytes) / (1024 * 1024) > settings.max_image_mb:
            raise InvalidImagePayloadError(f"image exceeds {settings.max_image_mb}MB")
        pipeline = FaceVerificationPipeline()
        faces = pipeline._get_detector().detect(image_bytes, None)
        pipeline._validate_quality(faces, request.quality_policy, "image")
        return {"request_id": request.request_id, "faces": [face.model_dump() for face in faces]}
    except FaceQualityError as exc:
        raise HTTPException(status_code=422, detail={"request_id": request.request_id, "error": {"code": exc.code, "message": exc.message}}) from exc
    except InvalidImagePayloadError as exc:
        raise HTTPException(status_code=415, detail={"request_id": request.request_id, "error": {"code": "invalid_image_payload", "message": exc.message}}) from exc
    except DetectorProviderError as exc:
        raise HTTPException(status_code=500, detail={"request_id": request.request_id, "error": {"code": "detector_provider_invalid", "message": exc.message}}) from exc


@router.post("/embed")
def embed_faces(request: EmbedRequest, _: None = Depends(require_bearer_token)) -> dict[str, object]:
    settings = get_settings()
    try:
        pipeline = FaceVerificationPipeline()
        image_bytes = ImageDecoder().decode(request.image.data, request.image.kind)
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
        raise HTTPException(status_code=422, detail={"request_id": request.request_id, "error": {"code": exc.code, "message": exc.message}}) from exc
    except InvalidImagePayloadError as exc:
        raise HTTPException(status_code=415, detail={"request_id": request.request_id, "error": {"code": "invalid_image_payload", "message": exc.message}}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"request_id": request.request_id, "error": {"code": "embedding_failed", "message": str(exc)}}) from exc
