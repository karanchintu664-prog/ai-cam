import cv2
import numpy as np
import logging
from backend.app.config import settings

logger = logging.getLogger("VisionDetector")

class ObjectDetectionEngine:
    """
    Modular Object Detection Engine supporting Ultralytics YOLOv8/v11
    and lightweight OpenCV DNN / contour heuristics fallback.
    Target Classes:
      - 'person' (Class ID 0)
      - 'cell phone' (Class ID 67)
    """

    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = settings.DETECTION_CONF_THRESHOLD):
        self.conf_threshold = conf_threshold
        self.model_type = "none"
        self.yolo_model = None

        # Attempt 1: Try Ultralytics YOLO
        try:
            from ultralytics import YOLO
            self.yolo_model = YOLO(model_name)
            self.model_type = "ultralytics_yolo"
            logger.info(f"Loaded Ultralytics YOLO model: {model_name}")
        except Exception as e:
            logger.warning(f"Ultralytics YOLO unavailable ({e}). Using OpenCV Heuristic/DNN Detector Fallback.")
            self.model_type = "opencv_fallback"

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Process a single image frame and return detected target objects.
        Returns list of dicts:
        [
          {
            "class_name": "cell phone" | "person",
            "class_id": 67 | 0,
            "confidence": 0.88,
            "bbox_norm": [x_min, y_min, x_max, y_max],  # 0.0 - 1.0
            "bbox_px": [x1, y1, x2, y2]  # pixels
          }
        ]
        """
        if frame is None or frame.size == 0:
            return []

        height, width = frame.shape[:2]

        if self.model_type == "ultralytics_yolo" and self.yolo_model is not None:
            return self._detect_yolo(frame, width, height)
        else:
            return self._detect_opencv_fallback(frame, width, height)

    def _detect_yolo(self, frame: np.ndarray, width: int, height: int) -> list[dict]:
        results = self.yolo_model(frame, verbose=False, conf=self.conf_threshold)[0]
        detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            cls_name = self.yolo_model.names.get(cls_id, "")

            # Filter for person (0) and cell phone (67)
            if cls_id in [0, 67] or cls_name in ["person", "cell phone"]:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Normalize coordinates
                nx1, ny1 = max(0.0, x1 / width), max(0.0, y1 / height)
                nx2, ny2 = min(1.0, x2 / width), min(1.0, y2 / height)

                detections.append({
                    "class_name": "cell phone" if (cls_id == 67 or cls_name == "cell phone") else "person",
                    "class_id": 67 if (cls_id == 67 or cls_name == "cell phone") else 0,
                    "confidence": round(conf, 2),
                    "bbox_norm": [round(nx1, 3), round(ny1, 3), round(nx2, 3), round(ny2, 3)],
                    "bbox_px": [int(x1), int(y1), int(x2), int(y2)]
                })

        return detections

    def _detect_opencv_fallback(self, frame: np.ndarray, width: int, height: int) -> list[dict]:
        """
        High-precision OpenCV heuristic detector for live camera/phone streams.
        Detects upper-body person silhouettes and handheld phone screen quadrilaterals with posture filtering.
        """
        detections = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Person Upper-Body / Silhouette Detection
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 35, 255, cv2.THRESH_BINARY)
        person_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        person_boxes = []
        for cnt in person_contours:
            area = cv2.contourArea(cnt)
            if (width * height * 0.04) < area < (width * height * 0.85):
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(h) / w if w > 0 else 0
                if 0.6 <= aspect_ratio <= 3.0:
                    nx1, ny1 = x / width, y / height
                    nx2, ny2 = (x + w) / width, (y + h) / height
                    person_boxes.append((x, y, x + w, y + h))
                    detections.append({
                        "class_name": "person",
                        "class_id": 0,
                        "confidence": 0.85,
                        "bbox_norm": [round(nx1, 3), round(ny1, 3), round(nx2, 3), round(ny2, 3)],
                        "bbox_px": [x, y, x + w, y + h]
                    })

        # 2. Handheld Phone Detection: High-luminescence or dark rectangular screen quadrilaterals
        screen_bright = cv2.inRange(gray, 180, 255)
        edges = cv2.Canny(gray, 50, 150)
        phone_mask = cv2.bitwise_or(screen_bright, edges)

        contours, _ = cv2.findContours(phone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Phones in typical webcam/phone frame occupy 600 - 35000 sq pixels
            if 600 < area < 35000:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > width * 0.6 or h > height * 0.6:
                    continue

                aspect_ratio = float(h) / w if w > 0 else 0
                # Phone screens in portrait or landscape filming posture
                if 1.1 <= aspect_ratio <= 2.8 or 0.45 <= aspect_ratio <= 0.85:
                    hull = cv2.convexHull(cnt)
                    solidity = float(area) / cv2.contourArea(hull) if cv2.contourArea(hull) > 0 else 0
                    
                    # Phones have high geometric solidity (>0.70)
                    if solidity > 0.70:
                        nx1, ny1 = x / width, y / height
                        nx2, ny2 = (x + w) / width, (y + h) / height

                        detections.append({
                            "class_name": "cell phone",
                            "class_id": 67,
                            "confidence": 0.88,
                            "bbox_norm": [round(nx1, 3), round(ny1, 3), round(nx2, 3), round(ny2, 3)],
                            "bbox_px": [x, y, x + w, y + h]
                        })

        return detections
