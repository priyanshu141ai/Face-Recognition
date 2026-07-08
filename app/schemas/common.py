from pydantic import BaseModel, Field


class ImagePayload(BaseModel):
    kind: str = Field(..., pattern="^(base64_jpeg|base64_png)$")
    data: str = Field(..., min_length=1)


class QualityPolicy(BaseModel):
    reject_if_no_face: bool = True
    reject_if_multiple_faces: bool = True
    min_detection_confidence: float = 0.85
