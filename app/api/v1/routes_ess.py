from dataclasses import dataclass

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import (
    abuse_service,
    attempt_service,
    audit_service,
    device_proof_service,
    liveness_service,
    repository_dependency,
)
from app.core.config import get_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.ess_security import require_device_id, require_device_reset_token, require_user_id
from app.core.gateway_security import gateway_action, require_body_binding
from app.core.security import require_bearer_token
from app.core.security_errors import SecurityDomainError
from app.schemas.ess import (
    ClientCreateRequest,
    ClientCreateResponse,
    ClientListResponse,
    ClientValidateRequest,
    ClientValidateResponse,
    DeviceChallengeRequest,
    DeviceChallengeResponse,
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceResetRequest,
    DeviceResetResponse,
    DeviceRevokeRequest,
    DeviceRevokeResponse,
    DeviceRotateRequest,
    DeviceRotateResponse,
    DeviceStatusResponse,
    DeviceVerifyRequest,
    DeviceVerifyResponse,
    FaceRegisterRequest,
    FaceRegisterResponse,
    FaceLifecycleRequest,
    FaceLifecycleResponse,
    FaceStatusResponse,
    FaceVerifyRegisteredRequest,
    FaceVerifyResponse,
)
from app.schemas.liveness import DeviceProof
from app.schemas.gateway import GatewayAssertionClaims
from app.services.biometric_crypto import (
    BiometricCipher,
    BiometricKeyMissingError,
    BiometricTemplateInvalidError,
)
from app.services.device_proof import ALGORITHM, DeviceProofService, canonical_payload, validate_public_key
from app.services.ess_repository import (
    ClientCodeConflictError,
    DeviceAlreadyRegisteredError,
    DeviceAssignedToAnotherUserError,
    DeviceKeyConflictError,
    EssRepository,
    FaceAlreadyRegisteredError,
)
from app.services.face_enrollment import extract_face_template, extract_fused_face_template
from app.services.image_decoder import ImageDecoder
from app.services.matcher import FaceMatcher


router = APIRouter(tags=["ess"])
_repository = repository_dependency


@dataclass(frozen=True)
class BoundDeviceContext:
    user_id: str
    device_id: str


def _require_bound_device(
    user_id: str = Depends(require_user_id),
    device_id: str = Depends(require_device_id),
    repository: EssRepository = Depends(_repository),
) -> BoundDeviceContext:
    if not repository.is_device_bound(user_id, device_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "device_not_authorized", "message": "This device is not authorized for the user"},
        )
    return BoundDeviceContext(user_id=user_id, device_id=device_id)


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


def _check_rate(
    http_request: Request,
    repository: EssRepository,
    action: str,
    limit: int,
    window_seconds: int,
    *,
    user_id: str | None = None,
    device_id: str | None = None,
) -> None:
    abuse_service(repository).check(
        http_request,
        action,
        limit=limit,
        window_seconds=window_seconds,
        user_id=user_id,
        device_id=device_id,
    )


def _verify_existing_device_proof(
    repository: EssRepository,
    user_id: str,
    device_id: str,
    operation: str,
    proof: DeviceProof | None,
) -> None:
    settings = get_settings()
    if not settings.device_proof_required and settings.allow_legacy_device_id_only:
        return
    record = repository.get_device_security(user_id, device_id)
    if not record or not record.get("public_key"):
        raise SecurityDomainError(
            "device_public_key_missing",
            "This device must be registered with a cryptographic public key.",
            status_code=403,
        )
    try:
        device_proof_service(repository).verify(
            proof,
            user_id=user_id,
            device_id=device_id,
            operation=operation,
            public_key_pem=str(record["public_key"]),
        )
    except SecurityDomainError as exc:
        audit_service(repository).record(
            "device_signature_failed", "blocked", user_id=user_id, device_id=device_id, reason_code=exc.code
        )
        raise


FaceSecurityRequest = FaceRegisterRequest | FaceVerifyRegisteredRequest


def _decode_liveness_frames(request: FaceSecurityRequest, operation: str) -> list[bytes]:
    settings = get_settings()
    decoder = ImageDecoder(settings.max_image_pixels)
    if request.liveness is None:
        if operation != "face_verify":
            return []
        if not settings.allow_legacy_single_image_verification:
            raise SecurityDomainError("challenge_missing", "A liveness challenge is required.", status_code=422)
        if request.image is None:
            raise InvalidImagePayloadError("image payload is required")
        value = decoder.decode(
            request.image.data, request.image.kind, int(settings.max_image_mb * 1024 * 1024)
        )
        if len(value) > settings.max_image_mb * 1024 * 1024:
            raise InvalidImagePayloadError(f"image exceeds {settings.max_image_mb}MB")
        return [value]

    frame_bytes = []
    for frame in request.liveness.frames:
        value = decoder.decode(
            frame.data, frame.kind, int(settings.max_image_mb * 1024 * 1024)
        )
        if len(value) > settings.max_image_mb * 1024 * 1024:
            raise InvalidImagePayloadError(f"image exceeds {settings.max_image_mb}MB")
        frame_bytes.append(value)
    return frame_bytes


def _secure_face_request(
    request: FaceSecurityRequest,
    context: BoundDeviceContext,
    repository: EssRepository,
    operation: str,
) -> list[bytes]:
    proof = request.device_proof or (request.liveness.device_proof if request.liveness else None)
    _verify_existing_device_proof(repository, context.user_id, context.device_id, operation, proof)
    frames = _decode_liveness_frames(request, operation)
    if request.liveness is not None:
        liveness_service(repository).evaluate(
            request.liveness,
            user_id=context.user_id,
            device_id=context.device_id,
            frame_bytes=frames,
            intended_action=operation,
        )
    elif get_settings().liveness_required:
        raise SecurityDomainError("challenge_missing", "A liveness challenge is required.", status_code=422)
    return frames


@router.post("/api/clients", status_code=status.HTTP_201_CREATED, response_model=ClientCreateResponse)
def create_client(
    request: ClientCreateRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("client_create", require_active_device=False)),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    settings = get_settings()
    _check_rate(http_request, repository, "client_create", settings.client_create_limit_per_hour, 3600)
    try:
        return repository.create_client(request.code, request.name.strip(), request.active)
    except ClientCodeConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": "client_code_exists", "message": str(exc)}) from exc


@router.get("/api/clients", response_model=ClientListResponse)
def list_clients(
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("client_list", require_active_device=False)),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    items = repository.list_clients()
    return {"items": items, "count": len(items)}


@router.post("/api/public/clients/validate", response_model=ClientValidateResponse)
def validate_client_code(
    request: ClientValidateRequest,
    http_request: Request,
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    settings = get_settings()
    _check_rate(
        http_request,
        repository,
        "client_validate",
        settings.client_validation_rate_limit_per_minute,
        60,
    )
    client = repository.validate_client(request.code)
    return {"valid": client is not None, "client": client}


@router.post("/api/ess/device/challenge", response_model=DeviceChallengeResponse)
def issue_device_challenge(
    request: DeviceChallengeRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_challenge:*", require_active_device=False)),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    require_body_binding(gateway, device_id=request.device_id)
    if gateway is not None and gateway.action != f"device_challenge:{request.operation}":
        raise SecurityDomainError("gateway_action_mismatch", "Gateway action does not match the requested device operation.", status_code=403)
    settings = get_settings()
    _check_rate(http_request, repository, "device_challenge", settings.device_verify_limit_per_minute, 60, user_id=user_id, device_id=request.device_id)
    if request.operation != "register" and not repository.is_device_bound(user_id, request.device_id):
        raise SecurityDomainError("device_not_authorized", "This device is not authorized for the user.", status_code=403)
    if gateway is not None and request.operation != "register":
        record = repository.get_device_security(user_id, request.device_id)
        if not record or int(record.get("key_version") or 0) != gateway.device_key_version:
            raise SecurityDomainError("device_key_version_mismatch", "The asserted device key version is stale.", status_code=403)
    challenge = device_proof_service(repository).issue(user_id, request.device_id, request.operation)
    return {
        **challenge.__dict__,
        "canonical_payload_version": "v1",
        "canonical_payload": canonical_payload(challenge.__dict__, challenge.nonce).decode("utf-8"),
    }


@router.post("/api/ess/device/register", status_code=status.HTTP_201_CREATED, response_model=DeviceRegisterResponse)
def register_device(
    request: DeviceRegisterRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_register", require_active_device=False)),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    require_body_binding(gateway, device_id=request.device_id, platform=request.platform)
    if gateway is not None and gateway.device_key_version != 0:
        raise SecurityDomainError("device_key_version_mismatch", "Initial device registration requires key version zero.", status_code=403)
    settings = get_settings()
    _check_rate(http_request, repository, "device_register", settings.device_register_limit_per_hour, 3600, user_id=user_id, device_id=request.device_id)
    fingerprint = algorithm = None
    if request.public_key:
        _, fingerprint = validate_public_key(request.public_key)
        algorithm = ALGORITHM
    if settings.device_proof_required or not settings.allow_legacy_device_id_only:
        if not request.public_key:
            raise SecurityDomainError("device_public_key_required", "A P-256 public key is required.", status_code=422)
        try:
            verified = device_proof_service(repository).verify(
                request.device_proof,
                user_id=user_id,
                device_id=request.device_id,
                operation="register",
                public_key_pem=request.public_key,
            )
        except SecurityDomainError as exc:
            audit_service(repository).record(
                "device_signature_failed", "blocked", user_id=user_id,
                device_id=request.device_id, reason_code=exc.code
            )
            raise
        if verified != fingerprint:
            raise SecurityDomainError("device_public_key_invalid", "The device public key is invalid.", status_code=422)
    try:
        registration = repository.register_device(
            user_id,
            request.device_id,
            request.platform,
            request.public_key,
            public_key_fingerprint=fingerprint,
            key_algorithm=algorithm,
        )
    except DeviceAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail={"code": "user_device_conflict", "message": str(exc)}) from exc
    except DeviceAssignedToAnotherUserError as exc:
        raise HTTPException(status_code=409, detail={"code": "device_user_conflict", "message": str(exc)}) from exc
    except DeviceKeyConflictError as exc:
        raise SecurityDomainError("device_key_conflict", str(exc), status_code=409) from exc
    audit_service(repository).record("device_registered", "allowed", user_id=user_id, device_id=request.device_id)
    return {"registered": True, **registration}


@router.post("/api/ess/device/verify", response_model=DeviceVerifyResponse)
def verify_device(
    request: DeviceVerifyRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_verify")),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, bool]:
    require_body_binding(gateway, device_id=request.device_id)
    settings = get_settings()
    _check_rate(http_request, repository, "device_verify", settings.device_verify_limit_per_minute, 60, user_id=user_id, device_id=request.device_id)
    if not repository.is_device_bound(user_id, request.device_id):
        raise HTTPException(status_code=403, detail={"code": "device_not_authorized", "message": "This device is not authorized for the user"})
    _verify_existing_device_proof(repository, user_id, request.device_id, "verify", request.device_proof)
    repository.verify_device(user_id, request.device_id)
    audit_service(repository).record("device_verified", "allowed", user_id=user_id, device_id=request.device_id)
    return {"verified": True}


@router.get("/api/ess/device/status", response_model=DeviceStatusResponse)
def device_status(
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_status", require_active_device=False)),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    registration = repository.get_device(user_id)
    session_state = None
    if gateway is not None:
        if registration is None:
            session_state = "registration_required"
        elif registration["device_id"] != gateway.device_id:
            session_state = "device_change_required"
        elif int(registration.get("key_version") or 0) != gateway.device_key_version:
            session_state = "key_refresh_required"
        else:
            session_state = "active"
    return {"registered": registration is not None, "device": registration, "session_state": session_state}


@router.post("/api/ess/device/rotate", response_model=DeviceRotateResponse)
def rotate_device_key(
    request: DeviceRotateRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_rotate")),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    require_body_binding(gateway, device_id=request.device_id)
    settings = get_settings()
    _check_rate(
        http_request, repository, "device_rotate", settings.device_rotate_limit_per_hour, 3600,
        user_id=user_id, device_id=request.device_id
    )
    _verify_existing_device_proof(repository, user_id, request.device_id, "rotate", request.device_proof)
    _, fingerprint = validate_public_key(request.new_public_key)
    try:
        version = repository.rotate_device_key(user_id, request.device_id, request.new_public_key, fingerprint, ALGORITHM)
    except DeviceKeyConflictError as exc:
        raise SecurityDomainError("device_key_conflict", str(exc), status_code=409) from exc
    if version is None:
        raise SecurityDomainError("device_not_authorized", "This device is not authorized for the user.", status_code=403)
    audit_service(repository).record("device_key_rotated", "allowed", user_id=user_id, device_id=request.device_id)
    return {"rotated": True, "key_version": version}


@router.post("/api/ess/device/revoke", response_model=DeviceRevokeResponse)
def revoke_device(
    request: DeviceRevokeRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_revoke")),
    user_id: str = Depends(require_user_id),
    repository: EssRepository = Depends(_repository),
) -> dict[str, bool]:
    require_body_binding(gateway, device_id=request.device_id)
    settings = get_settings()
    _check_rate(
        http_request, repository, "device_revoke", settings.device_revoke_limit_per_hour, 3600,
        user_id=user_id, device_id=request.device_id
    )
    _verify_existing_device_proof(repository, user_id, request.device_id, "revoke", request.device_proof)
    revoked = repository.revoke_device(user_id, request.device_id)
    audit_service(repository).record("device_revoked", "allowed", user_id=user_id, device_id=request.device_id, reason_code="user_requested")
    return {"revoked": revoked}


@router.post("/api/ess/device/reset", response_model=DeviceResetResponse)
def reset_device(
    http_request: Request,
    request: DeviceResetRequest | None = None,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("device_reset", require_active_device=False)),
    user_id: str = Depends(require_user_id),
    __: None = Depends(require_device_reset_token),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    settings = get_settings()
    _check_rate(http_request, repository, "device_reset", settings.device_reset_limit_per_hour, 3600, user_id=user_id)
    reset = repository.reset_device(user_id)
    audit_service(repository).record(
        "device_admin_reset", "allowed", user_id=user_id, reason_code="reason_supplied" if request and request.reason else "reason_missing"
    )
    return {"reset": reset}


@router.post(
    "/api/ess/face/register",
    status_code=status.HTTP_201_CREATED,
    response_model=FaceRegisterResponse,
    responses={
        409: {
            "description": "An active face template already exists.",
            "content": {"application/json": {"example": {
                "detail": {"code": "face_already_registered", "message": "A face is already registered for this user"}
            }}},
        },
        422: {
            "description": "Invalid angles, capture quality, or identity consistency.",
            "content": {"application/json": {"examples": {
                "invalid_angles": {"value": {"detail": {
                    "code": "invalid_enrollment_angles",
                    "message": "Enrollment requires front, left, and right captures.",
                }}},
                "duplicate_angle": {"value": {"detail": {
                    "code": "duplicate_enrollment_angle",
                    "message": "Each enrollment angle must be provided once.",
                }}},
                "quality_rejected": {"value": {"detail": {
                    "code": "face_quality_rejected",
                    "message": "face quality rejected for left enrollment capture",
                }}},
                "identity_mismatch": {"value": {"detail": {
                    "code": "enrollment_identity_mismatch",
                    "message": "Enrollment captures do not appear to show the same person.",
                }}},
            }}},
        },
    },
)
def register_face(
    request: FaceRegisterRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_register")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    require_body_binding(gateway, request_id=request.request_id)
    settings = get_settings()
    _check_rate(http_request, repository, "face_register", settings.face_register_limit_per_hour, 3600, user_id=context.user_id, device_id=context.device_id)
    try:
        _secure_face_request(request, context, repository, "face_register")
        extracted = extract_fused_face_template(request, settings.max_image_mb)
        encrypted = _cipher().encrypt(extracted.embedding.astype("<f4", copy=False).tobytes())
        registered_at = repository.register_face(
            user_id=context.user_id,
            encrypted_embedding=encrypted,
            embedding_dimension=int(extracted.embedding.size),
            detector=extracted.detector,
            recognizer=extracted.recognizer,
            preprocessing=extracted.preprocessing,
            consent_reference=request.consent_reference,
            calibration_version=extracted.calibration_version,
            encryption_key_version=settings.biometric_encryption_key_version,
            capture_count=extracted.capture_count,
            captured_angles=",".join(angle.value for angle in extracted.captured_angles),
            template_version=extracted.template_version,
        )
    except FaceAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail={"code": "face_already_registered", "message": str(exc)}) from exc
    except (FaceQualityError, InvalidImagePayloadError, ValueError) as exc:
        raise _face_error(exc) from exc
    audit_service(repository).record("face_registered", "allowed", user_id=context.user_id, device_id=context.device_id, request_id=request.request_id)
    return {
        "registered": True,
        "status": "registered",
        "user_id": context.user_id,
        "capture_count": extracted.capture_count,
        "captured_angles": list(extracted.captured_angles),
        "template_version": extracted.template_version,
        "registered_at": registered_at,
        "model": {"detector": extracted.detector, "recognizer": extracted.recognizer, "preprocessing": extracted.preprocessing},
    }


@router.get("/api/ess/face/status", response_model=FaceStatusResponse)
def face_registration_status(
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_status")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    record = repository.get_face_status(context.user_id)
    if record is None:
        return {
            "registered": False, "status": "not_registered", "capture_count": 0,
            "captured_angles": [], "template_version": None, "registered_at": None, "model": None,
        }
    captured_angles = [
        angle for angle in str(record.get("captured_angles") or "").split(",")
        if angle in {"front", "left", "right"}
    ]
    if record.get("deleted_at") is not None:
        return {
            "registered": False, "status": "not_registered", "capture_count": 0,
            "captured_angles": [], "template_version": None, "registered_at": None, "model": None,
        }
    if record.get("revoked_at") is not None:
        return {
            "registered": False, "status": "revoked", "capture_count": int(record["capture_count"]),
            "captured_angles": captured_angles, "template_version": record["template_version"],
            "registered_at": record["registered_at"], "model": None,
        }
    return {
        "registered": True,
        "status": "registered",
        "capture_count": int(record["capture_count"]),
        "captured_angles": captured_angles,
        "template_version": record["template_version"],
        "registered_at": record["registered_at"],
        "model": {"detector": record["detector"], "recognizer": record["recognizer"], "preprocessing": record["preprocessing"]},
    }


@router.post("/api/ess/face/revoke", response_model=FaceLifecycleResponse)
def revoke_face_registration(
    request: FaceLifecycleRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_revoke")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(_repository),
) -> dict[str, bool]:
    settings = get_settings()
    _check_rate(
        http_request, repository, "face_revoke", settings.face_lifecycle_limit_per_hour, 3600,
        user_id=context.user_id, device_id=context.device_id
    )
    _verify_existing_device_proof(
        repository, context.user_id, context.device_id, "face_revoke", request.device_proof
    )
    changed = repository.revoke_face(context.user_id)
    audit_service(repository).record(
        "face_revoked", "allowed", user_id=context.user_id, device_id=context.device_id,
        reason_code="user_requested"
    )
    return {"changed": changed}


@router.post("/api/ess/face/delete", response_model=FaceLifecycleResponse)
def delete_face_registration(
    request: FaceLifecycleRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_delete")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(_repository),
) -> dict[str, bool]:
    settings = get_settings()
    _check_rate(
        http_request, repository, "face_delete", settings.face_lifecycle_limit_per_hour, 3600,
        user_id=context.user_id, device_id=context.device_id
    )
    _verify_existing_device_proof(
        repository, context.user_id, context.device_id, "face_delete", request.device_proof
    )
    changed = repository.delete_face(context.user_id)
    audit_service(repository).record(
        "face_deleted", "allowed", user_id=context.user_id, device_id=context.device_id,
        reason_code="user_requested"
    )
    return {"changed": changed}


@router.post("/api/ess/face/verify", response_model=FaceVerifyResponse)
def verify_registered_face(
    request: FaceVerifyRegisteredRequest,
    http_request: Request,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("face_verify")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(_repository),
) -> dict[str, object]:
    require_body_binding(gateway, request_id=request.request_id)
    settings = get_settings()
    attempts = attempt_service(repository)
    attempts.ensure_allowed(context.user_id, context.device_id)
    _check_rate(http_request, repository, "face_verify", settings.face_verify_limit_per_minute, 60, user_id=context.user_id, device_id=context.device_id)
    record = repository.get_face(context.user_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "face_not_registered", "message": "No face is registered for this user"})
    try:
        _secure_face_request(request, context, repository, "face_verify")
        selected = request if request.image is not None else request.model_copy(
            update={"image": request.liveness.frames[0] if request.liveness else None}
        )
        extracted = extract_face_template(selected, settings.max_image_mb)
        if extracted.recognizer != record["recognizer"]:
            raise HTTPException(status_code=409, detail={"code": "face_model_changed", "message": "The registered face must be enrolled again for the active model"})
        if int(record["encryption_key_version"]) != settings.biometric_encryption_key_version:
            raise HTTPException(
                status_code=503,
                detail={"code": "biometric_key_version_mismatch", "message": "Biometric key rotation is incomplete"},
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
    if decision == "match":
        attempts.success(context.user_id, context.device_id)
        audit_service(repository).record(
            "face_verification_succeeded", "allowed", user_id=context.user_id,
            device_id=context.device_id, request_id=request.request_id,
        )
    else:
        attempts.failure(context.user_id, context.device_id)
        audit_service(repository).record("face_verification_failed", "rejected", user_id=context.user_id, device_id=context.device_id, request_id=request.request_id, reason_code="non_match")
    return {"verified": decision == "match", "decision": decision, "similarity_cosine": round(similarity, 6), "threshold": matcher.threshold}
