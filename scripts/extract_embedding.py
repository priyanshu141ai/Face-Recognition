import argparse
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.services.alignment import FaceAligner
from app.services.image_decoder import ImageDecoder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    settings = get_settings()
    decoder = ImageDecoder()
    detector = YuNetFaceDetector() if settings.detector_provider == "yunet" else None
    recognizer = ArcFaceOnnxRecognizer()
    aligner = FaceAligner()

    image_bytes = Path(args.image).read_bytes()
    image = decoder.decode_image_to_array(image_bytes)
    detections = detector.detect(image_bytes) if detector else []
    if not detections:
        raise SystemExit("No face detected")

    aligned = aligner.align_face_112(image, detections[0].landmarks5)
    embedding = recognizer.embed(aligned)
    np.save(args.output, embedding)
    print({"shape": embedding.shape, "l2_norm": float(np.linalg.norm(embedding))})


if __name__ == "__main__":
    main()
