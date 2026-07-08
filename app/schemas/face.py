from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import ImagePayload, QualityPolicy


class VerifyRequest(BaseModel):
    request_id: str | None = None
    image_a: ImagePayload
    image_b: ImagePayload
    face_selector: Literal["largest"] = "largest"
    return_embeddings: bool = False
    quality_policy: QualityPolicy = QualityPolicy()


class FaceDetectionSchema(BaseModel):
    bbox_xywh: list[float]
    landmarks5: list[list[float]]
    detection_confidence: float


class VerifyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    request_id: str | None = None
    decision: Literal["match", "non_match"]
    match_score_percent: float
    similarity_cosine: float
    threshold: dict[str, object]
    model_versions: dict[str, str]
    faces: dict[str, list[FaceDetectionSchema]]
    timings_ms: dict[str, float]
