import base64
import binascii
import io

import cv2
import numpy as np
from PIL import Image

from app.core.errors import InvalidImagePayloadError


class ImageDecoder:
    def __init__(self, max_image_pixels: int = 20_000_000) -> None:
        self.max_image_pixels = max_image_pixels

    @staticmethod
    def validate_encoded_size(payload: str, max_decoded_bytes: int | None) -> None:
        if max_decoded_bytes is None or len(payload) % 4:
            return
        padding = len(payload) - len(payload.rstrip("="))
        if len(payload) // 4 * 3 - padding > max_decoded_bytes:
            raise InvalidImagePayloadError("image exceeds the allowed size")

    def decode(self, payload: str, kind: str, max_decoded_bytes: int | None = None) -> bytes:
        if not payload:
            raise InvalidImagePayloadError("empty image payload")
        self.validate_encoded_size(payload, max_decoded_bytes)
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImagePayloadError("invalid base64 data") from exc
        if not data:
            raise InvalidImagePayloadError("empty image payload")
        try:
            image = Image.open(io.BytesIO(data))
            if image.width * image.height > self.max_image_pixels:
                raise InvalidImagePayloadError("image pixel dimensions exceed the allowed limit")
            image.verify()
        except InvalidImagePayloadError:
            raise
        except Exception as exc:
            raise InvalidImagePayloadError("invalid image payload") from exc
        if kind == "base64_jpeg" and (image.format or "").upper() != "JPEG":
            raise InvalidImagePayloadError("jpeg payload expected")
        if kind == "base64_png" and (image.format or "").upper() != "PNG":
            raise InvalidImagePayloadError("png payload expected")
        return data

    def decode_image_to_array(self, image_bytes: bytes) -> np.ndarray:
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if decoded is None:
            raise InvalidImagePayloadError("invalid image payload")
        return decoded
