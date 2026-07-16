import os
import threading
from typing import Any

import cv2
import numpy as np

from app.core.config import Settings, get_settings
from app.schemas.face import FaceDetectionSchema
from app.services.detector_base import BaseFaceDetector


class YuNetFaceDetector(BaseFaceDetector):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.detector = None
        self._detector_lock = threading.Lock()
        self._load_detector()

    def _load_detector(self) -> None:
        model_path = self.settings.yunet_model_path
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                "YuNet model not found. Please place face_detection_yunet_2023mar.onnx inside the models/ directory."
            )
        self.detector = cv2.FaceDetectorYN.create(
            model_path,
            "",
            (320, 320),
            self.settings.yunet_score_threshold,
            self.settings.yunet_nms_threshold,
            self.settings.yunet_top_k,
        )

    def detect(self, image: bytes, quality_policy: Any | None = None) -> list[FaceDetectionSchema]:
        image_array = np.frombuffer(image, dtype=np.uint8)
        image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image_bgr is None:
            return []

        height, width = image_bgr.shape[:2]
        if max(width, height) > self.settings.max_image_dimension:
            scale = self.settings.max_image_dimension / max(width, height)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            image_bgr = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
            width, height = new_w, new_h
        else:
            scale = 1.0

        with self._detector_lock:
            if self.detector is None:
                self._load_detector()
            self.detector.setInputSize((width, height))
            detect_result = self.detector.detect(image_bgr)
        if isinstance(detect_result, tuple) and len(detect_result) == 2:
            first, second = detect_result
            faces = second if isinstance(first, (int, float)) else first
        else:
            faces = detect_result
        if faces is None:
            return []

        detections: list[FaceDetectionSchema] = []
        for row in faces:
            x, y, w, h = [float(v) for v in row[:4]]
            if w < self.settings.min_face_size or h < self.settings.min_face_size:
                continue
            score = float(row[14]) if len(row) > 14 else 0.0
            if score < self.settings.yunet_score_threshold:
                continue
            if quality_policy is not None and score < quality_policy.min_detection_confidence:
                continue
            landmarks = [
                [float(row[4]), float(row[5])],
                [float(row[6]), float(row[7])],
                [float(row[8]), float(row[9])],
                [float(row[10]), float(row[11])],
                [float(row[12]), float(row[13])],
            ]
            if scale != 1.0:
                x = x / scale
                y = y / scale
                w = w / scale
                h = h / scale
                landmarks = [[pt[0] / scale, pt[1] / scale] for pt in landmarks]
            detections.append(
                FaceDetectionSchema(
                    bbox_xywh=[round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                    landmarks5=[[round(pt[0], 2), round(pt[1], 2)] for pt in landmarks],
                    detection_confidence=round(score, 4),
                )
            )
        return detections
