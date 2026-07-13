from dataclasses import dataclass

import numpy as np

from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.schemas.ess import FaceRegisterRequest
from app.services.pipeline import FaceVerificationPipeline, get_face_verification_pipeline


@dataclass(frozen=True)
class ExtractedFace:
    embedding: np.ndarray
    detector: str
    recognizer: str
    threshold: float
    preprocessing: str = "align112_rgb_v1"


def extract_face_template(request: FaceRegisterRequest, max_image_mb: float) -> ExtractedFace:
    pipeline = get_face_verification_pipeline()
    with pipeline.inference_lock:
        return _extract_face_template(pipeline, request, max_image_mb)


def _extract_face_template(
    pipeline: FaceVerificationPipeline, request: FaceRegisterRequest, max_image_mb: float
) -> ExtractedFace:
    image_bytes = pipeline.decoder.decode(request.image.data, request.image.kind)
    if len(image_bytes) / (1024 * 1024) > max_image_mb:
        raise InvalidImagePayloadError(f"image exceeds {max_image_mb}MB")

    faces = pipeline._get_detector().detect(image_bytes, None)
    pipeline._validate_quality(faces, request.quality_policy, "image")
    selected = pipeline._select_faces(faces, request.face_selector, request.face_index)
    if not selected:
        raise FaceQualityError("no_face_detected", "face registration requires one detected face")

    aligned = pipeline.preprocessor.align_face(pipeline._decode_image_bytes(image_bytes), selected[0])
    embedding = np.asarray(pipeline._get_recognizer().embed(aligned), dtype=np.float32)
    if embedding.ndim != 1 or embedding.size == 0 or not np.all(np.isfinite(embedding)):
        raise ValueError("recognizer returned an invalid embedding")

    return ExtractedFace(
        embedding=embedding,
        detector=pipeline._detector_name(),
        recognizer=pipeline._recognizer_name(),
        threshold=pipeline.matcher.threshold,
    )
