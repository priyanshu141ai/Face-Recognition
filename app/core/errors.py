from fastapi import HTTPException, status


class FaceQualityError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidImagePayloadError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArcFaceModelNotFoundError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArcFaceInferenceError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidEmbeddingShapeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FaceAlignmentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RecognizerProviderError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DetectorProviderError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def http_error_from_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, FaceQualityError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error_code": exc.code, "message": exc.message})
    if isinstance(exc, InvalidImagePayloadError):
        return HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"error_code": "invalid_image_payload", "message": exc.message})
    if isinstance(exc, ArcFaceModelNotFoundError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "arcface_model_not_found", "message": exc.message})
    if isinstance(exc, ArcFaceInferenceError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "arcface_inference_failed", "message": exc.message})
    if isinstance(exc, InvalidEmbeddingShapeError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "invalid_embedding_shape", "message": exc.message})
    if isinstance(exc, FaceAlignmentError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "face_alignment_failed", "message": exc.message})
    if isinstance(exc, RecognizerProviderError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "recognizer_provider_invalid", "message": exc.message})
    if isinstance(exc, DetectorProviderError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "detector_provider_invalid", "message": exc.message})
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "internal_error", "message": "Internal server error"})
