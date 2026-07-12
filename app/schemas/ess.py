from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ImagePayload, QualityPolicy
from app.schemas.face import FaceSelector


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


class FaceRegisterRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=128)
    image: ImagePayload
    face_selector: FaceSelector = "largest"
    face_index: int | None = None
    quality_policy: QualityPolicy = Field(default_factory=QualityPolicy)


class FaceVerifyRegisteredRequest(FaceRegisterRequest):
    pass


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")
    platform: Literal["android", "ios", "web", "other"] = "other"
    public_key: str | None = Field(default=None, max_length=4096)


class DeviceVerifyRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255, pattern=r"^[A-Za-z0-9._:-]+$")


class DeviceResetRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
