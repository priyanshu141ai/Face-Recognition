import argparse
import os
import time
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.services.alignment import FaceAligner
from app.services.image_decoder import ImageDecoder
from app.services.matcher import FaceMatcher


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-a", required=True)
    parser.add_argument("--image-b", required=True)
    parser.add_argument("--save-crops", default=None)
    args = parser.parse_args()

    settings = get_settings()
    decoder = ImageDecoder()
    detector = YuNetFaceDetector() if settings.detector_provider == "yunet" else None
    recognizer = ArcFaceOnnxRecognizer()
    aligner = FaceAligner()
    matcher = FaceMatcher(threshold=settings.match_threshold)

    image_a_bytes = Path(args.image_a).read_bytes()
    image_b_bytes = Path(args.image_b).read_bytes()
    image_a = decoder.decode_image_to_array(image_a_bytes)
    image_b = decoder.decode_image_to_array(image_b_bytes)

    start = time.perf_counter()
    detections_a = detector.detect(image_a_bytes) if detector else []
    detections_b = detector.detect(image_b_bytes) if detector else []
    detect_ms = (time.perf_counter() - start) * 1000.0

    if not detections_a or not detections_b:
        raise SystemExit("No faces detected")

    align_start = time.perf_counter()
    aligned_a = aligner.align_face_112(image_a, detections_a[0].landmarks5)
    aligned_b = aligner.align_face_112(image_b, detections_b[0].landmarks5)
    align_ms = (time.perf_counter() - align_start) * 1000.0

    embed_start = time.perf_counter()
    emb_a = recognizer.embed(aligned_a)
    emb_b = recognizer.embed(aligned_b)
    embed_ms = (time.perf_counter() - embed_start) * 1000.0

    match_start = time.perf_counter()
    similarity = matcher.cosine_similarity(emb_a, emb_b)
    match_ms = (time.perf_counter() - match_start) * 1000.0

    if args.save_crops:
        output_dir = Path(args.save_crops)
        output_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_dir / "image_a.jpg"), aligned_a)
        cv2.imwrite(str(output_dir / "image_b.jpg"), aligned_b)

    print({
        "detections": {"image_a": len(detections_a), "image_b": len(detections_b)},
        "cosine_similarity": round(float(similarity), 6),
        "threshold": settings.match_threshold,
        "decision": matcher.decide(similarity),
        "timings_ms": {
            "detect": round(detect_ms, 2),
            "align": round(align_ms, 2),
            "embed": round(embed_ms, 2),
            "match": round(match_ms, 2),
        },
    })


if __name__ == "__main__":
    main()
