import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.ess_security import require_device_reset_token, require_user_id
from app.core.security import require_bearer_token
from app.schemas.ess import (
    ClientCreateRequest,
    ClientValidateRequest,
    DeviceRegisterRequest,
    DeviceResetRequest,
    DeviceVerifyRequest,
    FaceRegisterRequest,
    FaceVerifyRegisteredRequest,
)
from app.services.biometric_crypto import (
    BiometricCipher,
    BiometricKeyMissingError,
    BiometricTemplateInvalidError,
)
from app.services.ess_repository import (
    ClientCodeConflictError,
    DeviceAlreadyRegisteredError,
    DeviceAssignedToAnotherUserError,
    EssRepository,
    FaceAlreadyRegisteredError,
)
from app.services.face_enrollment import extract_face_template
from app.services.matcher import FaceMatcher


router = APIRouter(tags=["ess"])


def _repository() -> EssRepository:
    return EssRepository(get_settings().ess_database_path)


def _cipher() -> BiometricCipher:
    try:
        return BiometricCipher(get_settings().biometric_encryption_key)
    except BiometricKeyMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "biometric_encryption_not_configured", "message": str(exc)},
        ) from exc


def _face_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FaceQualityError):
        return HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message})
    if isinstance(exc, InvalidImagePayloadError):
        return HTTPException(status_code=415, detail={"code": "invalid_image_payload", "message": exc.message})
    return HTTPException(status_code=500, detail={"code": "face_processing_failed", "message": "Face processing failed"})


@router.post("/api/clients", status_code=status.HTTP_201_CREATED)
def create_client(
    request: ClientCreateRequest,
    _: None = Depends(require_bearer_token),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    try:
        return repository.create_client(request.code, request.name.strip(), request.active)
    except ClientCodeConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "client_code_exists", "message": str(exc)}) from exc


@router.get("/api/clients")
def list_clients(
    _: None = Depends(require_bearer_token),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    clients = repository.list_clients()
    return {"items": clients, "count": len(clients)}


@router.post("/api/public/clients/validate")
def validate_client_code(
    request: ClientValidateRequest,
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    client = repository.validate_client(request.code)
    if client is None:
        return {"valid": False, "client": None}
    return {"valid": True, "client": client}


@router.post("/api/ess/face/register", status_code=status.HTTP_201_CREATED)
def register_face(
    request: FaceRegisterRequest,
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    try:
        extracted = extract_face_template(request, get_settings().max_image_mb)
        encrypted = _cipher().encrypt(extracted.embedding.astype("<f4", copy=False).tobytes())
        registered_at = repository.register_face(
            user_id=user_id,
            encrypted_embedding=encrypted,
            embedding_dimension=int(extracted.embedding.size),
            detector=extracted.detector,
            recognizer=extracted.recognizer,
            preprocessing=extracted.preprocessing,
        )
    except FaceAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail={"code": "face_already_registered", "message": str(exc)}) from exc
    except (FaceQualityError, InvalidImagePayloadError, ValueError) as exc:
        raise _face_error(exc) from exc
    return {
        "registered": True,
        "user_id": user_id,
        "registered_at": registered_at,
        "model": {"detector": extracted.detector, "recognizer": extracted.recognizer, "preprocessing": extracted.preprocessing},
    }


@router.get("/api/ess/face/status")
def face_registration_status(
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    record = repository.get_face(user_id)
    if record is None:
        return {"registered": False, "registered_at": None, "model": None}
    return {
        "registered": True,
        "registered_at": record["registered_at"],
        "model": {
            "detector": record["detector"],
            "recognizer": record["recognizer"],
            "preprocessing": record["preprocessing"],
        },
    }


@router.post("/api/ess/face/verify")
def verify_registered_face(
    request: FaceVerifyRegisteredRequest,
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    record = repository.get_face(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "face_not_registered", "message": "No face is registered for this user"})
    try:
        extracted = extract_face_template(request, get_settings().max_image_mb)
        if extracted.recognizer != record["recognizer"]:
            raise HTTPException(
                status_code=409,
                detail={"code": "face_model_changed", "message": "The registered face must be enrolled again for the active model"},
            )
        decrypted = _cipher().decrypt(record["encrypted_embedding"])
        enrolled = np.frombuffer(decrypted, dtype="<f4")
        if enrolled.size != record["embedding_dimension"]:
            raise BiometricTemplateInvalidError("Stored biometric template has an invalid dimension")
        matcher = FaceMatcher(extracted.threshold)
        similarity = matcher.cosine_similarity(enrolled, extracted.embedding)
    except HTTPException:
        raise
    except (FaceQualityError, InvalidImagePayloadError, ValueError) as exc:
        raise _face_error(exc) from exc
    except BiometricTemplateInvalidError as exc:
        raise HTTPException(status_code=500, detail={"code": "biometric_template_invalid", "message": str(exc)}) from exc
    decision = matcher.decide(similarity)
    return {
        "verified": decision == "match",
        "decision": decision,
        "similarity_cosine": round(similarity, 6),
        "threshold": matcher.threshold,
    }


@router.post("/api/ess/device/register", status_code=status.HTTP_201_CREATED)
def register_device(
    request: DeviceRegisterRequest,
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    try:
        registration = repository.register_device(user_id, request.device_id, request.platform, request.public_key)
    except DeviceAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail={"code": "user_device_conflict", "message": str(exc)}) from exc
    except DeviceAssignedToAnotherUserError as exc:
        raise HTTPException(status_code=409, detail={"code": "device_user_conflict", "message": str(exc)}) from exc
    return {"registered": True, **registration}


@router.post("/api/ess/device/verify")
def verify_device(
    request: DeviceVerifyRequest,
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, bool]:
    if not repository.verify_device(user_id, request.device_id):
        raise HTTPException(status_code=403, detail={"code": "device_not_authorized", "message": "This device is not authorized for the user"})
    return {"verified": True}


@router.get("/api/ess/device/status")
def device_status(
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    registration = repository.get_device(user_id)
    return {"registered": registration is not None, "device": registration}


@router.post("/api/ess/device/reset")
def reset_device(
    request: DeviceResetRequest | None = None,
    _: None = Depends(require_bearer_token),
    user_id: str = Depends(require_user_id),
    __: None = Depends(require_device_reset_token),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    del request
    return {"reset": repository.reset_device(user_id)}
