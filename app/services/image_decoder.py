import base64
import binascii
import io
from PIL import Image

from app.core.errors import InvalidImagePayloadError


class ImageDecoder:
    def decode(self, payload: str, kind: str) -> bytes:
        if not payload:
            raise InvalidImagePayloadError("empty image payload")
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImagePayloadError("invalid base64 data") from exc
        if not data:
            raise InvalidImagePayloadError("empty image payload")
        try:
            image = Image.open(io.BytesIO(data))
            image.verify()
        except Exception as exc:
            raise InvalidImagePayloadError("invalid image payload") from exc
        if kind == "base64_jpeg" and (image.format or "").upper() != "JPEG":
            raise InvalidImagePayloadError("jpeg payload expected")
        if kind == "base64_png" and (image.format or "").upper() != "PNG":
            raise InvalidImagePayloadError("png payload expected")
        return data
