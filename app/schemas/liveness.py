from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ImagePayload


ChallengeType = Literal[
    "turn_head_left",
    "turn_head_right",
    "center_face",
    "multi_frame_capture",
]
LivenessAction = Literal["face_register", "face_verify"]


class DeviceProof(BaseModel):
    challenge_id: str = Field(min_length=36, max_length=36)
    nonce: str = Field(min_length=32, max_length=256)
    signature: str = Field(min_length=8, max_length=1024)


class LivenessChallengeRequest(BaseModel):
    intended_action: LivenessAction
    device_proof: DeviceProof | None = None


class LivenessChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    challenge_type: ChallengeType
    intended_action: LivenessAction
    issued_at: datetime
    expires_at: datetime
    required_capture_count: int


class LivenessEvidence(BaseModel):
    challenge_id: str = Field(min_length=36, max_length=36)
    challenge_nonce: str = Field(min_length=32, max_length=256)
    capture_timestamp: datetime
    challenge_action: ChallengeType
    frames: list[ImagePayload] = Field(min_length=1, max_length=10)
    provider_assertion: str | None = Field(default=None, max_length=8192)
    device_proof: DeviceProof | None = None


class LivenessResultSchema(BaseModel):
    approved: bool
    provider: str
    reason_code: str
