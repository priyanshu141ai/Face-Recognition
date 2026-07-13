from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceAttestationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=64)
    verdict: str = Field(min_length=1, max_length=128)
    checked_at: int
    app_identifier: str = Field(min_length=1, max_length=255)
    platform: Literal["android", "ios"]


class GatewayAssertionClaims(BaseModel):
    model_config = ConfigDict(extra="allow")

    iss: str = Field(min_length=1, max_length=255)
    aud: str | list[str]
    sub: str = Field(min_length=1, max_length=128)
    iat: int
    nbf: int
    exp: int
    jti: str = Field(min_length=8, max_length=255)
    tenant_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=8, max_length=255)
    action: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    http_method: str = Field(min_length=3, max_length=10)
    request_path: str = Field(min_length=1, max_length=512)
    device_key_version: int = Field(ge=0)
    session_id: str = Field(min_length=8, max_length=255)
    gateway_version: str = Field(min_length=1, max_length=64)
    device_attestation: DeviceAttestationClaim | None = None
    attendance_reference: str | None = Field(default=None, max_length=255)
    location_reference: str | None = Field(default=None, max_length=255)
