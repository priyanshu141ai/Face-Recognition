from dataclasses import dataclass

import numpy as np

from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.schemas.common import ImagePayload, QualityPolicy
from app.schemas.ess import EnrollmentAngle, FaceRegisterRequest, FaceVerifyRegisteredRequest
from app.services.pipeline import FaceVerificationPipeline, get_face_verification_pipeline


THREE_ANGLE_TEMPLATE_VERSION = "three_angle_mean_l2_v1"
THREE_ANGLE_ORDER = (EnrollmentAngle.FRONT, EnrollmentAngle.LEFT, EnrollmentAngle.RIGHT)


@dataclass(frozen=True)
class ExtractedFace:
    embedding: np.ndarray
    detector: str
    recognizer: str
    threshold: float
    preprocessing: str = "align112_rgb_v1"
    calibration_version: str = "linear_fallback_v1"


@dataclass(frozen=True)
class FusedEnrollmentTemplate(ExtractedFace):
    capture_count: int = 3
    captured_angles: tuple[EnrollmentAngle, ...] = THREE_ANGLE_ORDER
    template_version: str = THREE_ANGLE_TEMPLATE_VERSION


def extract_face_template(request: FaceVerifyRegisteredRequest, max_image_mb: float) -> ExtractedFace:
    pipeline = get_face_verification_pipeline()
    with pipeline.inference_slot():
        if request.image is None:
            raise InvalidImagePayloadError("image payload is required")
        image_bytes = _decode_image(
            pipeline,
            request.image,
            max_image_mb,
            "verification",
        )
        embedding = _extract_embedding(
            pipeline,
            image_bytes,
            request.quality_policy,
            request.face_selector,
            request.face_index,
            "verification",
        )
        return _result(pipeline, embedding)


def extract_fused_face_template(
    request: FaceRegisterRequest, max_image_mb: float
) -> FusedEnrollmentTemplate:
    pipeline = get_face_verification_pipeline()
    captures = {capture.angle: capture for capture in request.enrollment_images}
    with pipeline.inference_slot():
        embeddings = []
        for angle in THREE_ANGLE_ORDER:
            image_bytes = _decode_image(
                pipeline, captures[angle].image, max_image_mb,
                f"{angle.value} enrollment capture",
            )
            embeddings.append(_extract_embedding(
                pipeline,
                image_bytes,
                request.quality_policy,
                request.face_selector,
                request.face_index,
                f"{angle.value} enrollment capture",
            ))
            del image_bytes
        threshold = pipeline.matcher.threshold
        if any(
            pipeline.matcher.cosine_similarity(embeddings[left], embeddings[right]) < threshold
            for left in range(3)
            for right in range(left + 1, 3)
        ):
            raise FaceQualityError(
                "enrollment_identity_mismatch",
                "Enrollment captures do not appear to show the same person.",
            )
        fused = _normalize(np.mean(np.stack(embeddings), axis=0, dtype=np.float32))
        result = _result(pipeline, fused)
        return FusedEnrollmentTemplate(**result.__dict__)


def _decode_image(
    pipeline: FaceVerificationPipeline,
    image: ImagePayload,
    max_image_mb: float,
    label: str,
) -> bytes:
    max_bytes = int(max_image_mb * 1024 * 1024)
    try:
        image_bytes = pipeline.decoder.decode(image.data, image.kind, max_bytes)
    except InvalidImagePayloadError as exc:
        raise InvalidImagePayloadError(f"Invalid {label} image payload.") from exc
    if len(image_bytes) > max_bytes:
        raise InvalidImagePayloadError(f"The {label} image exceeds the allowed size.")
    return image_bytes


def _extract_embedding(
    pipeline: FaceVerificationPipeline,
    image_bytes: bytes,
    quality_policy: QualityPolicy,
    face_selector: str,
    face_index: int | None,
    label: str,
) -> np.ndarray:
    faces = pipeline._get_detector().detect(image_bytes, None)
    pipeline._validate_quality(faces, quality_policy, label)
    selected = pipeline._select_faces(faces, face_selector, face_index)
    if not selected:
        raise FaceQualityError("no_face_detected", f"No face detected in {label}.")

    aligned = pipeline.preprocessor.align_face(pipeline._decode_image_bytes(image_bytes), selected[0])
    embedding = np.asarray(pipeline._get_recognizer().embed(aligned), dtype=np.float32)
    if embedding.ndim != 1 or embedding.size == 0 or not np.all(np.isfinite(embedding)):
        raise ValueError("recognizer returned an invalid embedding")
    return _normalize(embedding)


def _normalize(embedding: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(embedding))
    if not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError("recognizer returned an invalid embedding")
    return np.asarray(embedding / norm, dtype=np.float32)


def _result(pipeline: FaceVerificationPipeline, embedding: np.ndarray) -> ExtractedFace:
    return ExtractedFace(
        embedding=embedding,
        detector=pipeline._detector_name(),
        recognizer=pipeline._recognizer_name(),
        threshold=pipeline.matcher.threshold,
        calibration_version=pipeline.calibrator.version,
    )
