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


def http_error_from_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, FaceQualityError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error_code": exc.code, "message": exc.message})
    if isinstance(exc, InvalidImagePayloadError):
        return HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail={"error_code": "invalid_image_payload", "message": exc.message})
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "internal_error", "message": "Internal server error"})
