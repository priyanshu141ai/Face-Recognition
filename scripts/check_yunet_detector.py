import argparse
import os

import cv2
import numpy as np

from app.models.yunet_detector import YuNetFaceDetector


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--debug-output")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        raise SystemExit(f"Image not found: {args.image}")

    detector = YuNetFaceDetector()
    image_bytes = open(args.image, "rb").read()
    detections = detector.detect(image_bytes)

    print(f"Faces detected: {len(detections)}")
    for index, face in enumerate(detections):
        print(f"[{index}] bbox={face.bbox_xywh} landmarks={face.landmarks5} confidence={face.detection_confidence}")

    if args.debug_output:
        image = cv2.imread(args.image)
        if image is not None:
            for face in detections:
                x, y, w, h = [int(v) for v in face.bbox_xywh]
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                for landmark in face.landmarks5:
                    lx, ly = [int(v) for v in landmark]
                    cv2.circle(image, (lx, ly), 2, (0, 0, 255), -1)
            cv2.imwrite(args.debug_output, image)
            print(f"Debug image saved to {args.debug_output}")


if __name__ == "__main__":
    main()
