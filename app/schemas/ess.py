from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.schemas.common import ImagePayload, QualityPolicy
from app.schemas.face import FaceSelector
from app.schemas.liveness import DeviceProof, LivenessEvidence


class ClientCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    active: bool = True

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("code may contain only letters, numbers, hyphens, and underscores")
        return normalized


class ClientValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class EnrollmentAngle(str, Enum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"


class EnrollmentCapture(BaseModel):
    angle: EnrollmentAngle
    image: ImagePayload


class FaceRegisterRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=128)
    enrollment_images: list[EnrollmentCapture] = Field(min_length=3, max_length=3)
    face_selector: FaceSelector = "largest"
    face_index: int | None = None
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    liveness: LivenessEvidence | None = None
    device_proof: DeviceProof | None = None
    consent_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_enrollment_angles(self) -> "FaceRegisterRequest":
        angles = [capture.angle for capture in self.enrollment_images]
        if len(set(angles)) != len(angles):
            raise PydanticCustomError(
                "duplicate_enrollment_angle", "Each enrollment angle must be provided once."
            )
        if set(angles) != set(EnrollmentAngle):
            raise PydanticCustomError(
                "invalid_enrollment_angles", "Enrollment requires front, left, and right captures."
            )
        return self


class FaceVerifyRegisteredRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=128)
    image: ImagePayload | None = None
    face_selector: FaceSelector = "largest"
    face_index: int | None = None
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)
    liveness: LivenessEvidence | None = None
    device_proof: DeviceProof | None = None


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    platform: Literal["android", "ios", "web", "other"] = "other"
    public_key: str | None = Field(default=None, max_length=4096)
    device_proof: DeviceProof | None = None


class DeviceVerifyRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    device_proof: DeviceProof | None = None


class DeviceResetRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


DeviceOperation = Literal[
    "register",
    "verify",
    "liveness_challenge",
    "face_register",
    "face_verify",
    "rotate",
    "revoke",
    "face_revoke",
    "face_delete",
]


class DeviceChallengeRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    operation: DeviceOperation


class DeviceChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    user_id: str
    device_id: str
    operation: DeviceOperation
    issued_at: datetime
    expires_at: datetime
    canonical_payload_version: Literal["v1"] = "v1"
    canonical_payload: str


class DeviceRotateRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    new_public_key: str = Field(min_length=100, max_length=4096)
    device_proof: DeviceProof


class DeviceRotateResponse(BaseModel):
    rotated: bool
    key_version: int


class DeviceRevokeRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    reason: str = Field(min_length=3, max_length=500)
    device_proof: DeviceProof


class DeviceRevokeResponse(BaseModel):
    revoked: bool


class ClientSummary(BaseModel):
    id: str
    code: str
    name: str


class ClientRecord(ClientSummary):
    active: bool
    created_at: datetime
    updated_at: datetime | None = None


class ClientCreateResponse(ClientRecord):
    pass


class ClientListResponse(BaseModel):
    items: list[ClientRecord]
    count: int


class ClientValidateResponse(BaseModel):
    valid: bool
    client: ClientSummary | None


class FaceModelInfo(BaseModel):
    detector: str
    recognizer: str
    preprocessing: str


class FaceRegisterResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    registered: bool
    status: Literal["registered"]
    user_id: str
    capture_count: int
    captured_angles: list[EnrollmentAngle]
    template_version: str
    registered_at: datetime
    model: FaceModelInfo


class FaceStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    registered: bool
    status: Literal["registered", "not_registered", "revoked"]
    capture_count: int
    captured_angles: list[EnrollmentAngle]
    template_version: str | None
    registered_at: datetime | None
    model: FaceModelInfo | None


class FaceVerifyResponse(BaseModel):
    verified: bool
    decision: Literal["match", "non_match"]
    similarity_cosine: float
    threshold: float


class FaceLifecycleRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    device_proof: DeviceProof


class FaceLifecycleResponse(BaseModel):
    changed: bool


class DeviceRegisterResponse(BaseModel):
    registered: bool
    device_id: str
    platform: Literal["android", "ios", "web", "other"]
    registered_at: datetime
    already_registered: bool
    key_version: int = 1


class DeviceVerifyResponse(BaseModel):
    verified: bool


class DeviceInfo(BaseModel):
    device_id: str
    platform: Literal["android", "ios", "web", "other"]
    registered_at: datetime
    last_verified_at: datetime | None
    key_version: int = 1
    key_algorithm: str | None = None


class DeviceStatusResponse(BaseModel):
    registered: bool
    device: DeviceInfo | None
    session_state: Literal["registration_required", "active", "device_change_required", "key_refresh_required"] | None = None


class DeviceResetResponse(BaseModel):
    reset: bool
