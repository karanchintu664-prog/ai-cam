import time
import math
import numpy as np

class TrackedObject:
    def __init__(self, track_id: int, bbox_norm: list[float], class_name: str, confidence: float):
        self.track_id = track_id
        self.class_name = class_name
        self.confidence = confidence
        self.bbox_norm = bbox_norm  # [x1, y1, x2, y2]
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.history = [bbox_norm]  # Track historical centroids/bboxes
        self.disappeared_frames = 0

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_norm
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.first_seen

    def get_position_variance(self) -> float:
        """
        Calculates spatial movement variance. Low variance indicates a steady recording stance.
        """
        if len(self.history) < 3:
            return 0.0
        
        centroids = [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in self.history[-15:]]
        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]
        
        var_x = np.var(xs) if len(xs) > 1 else 0.0
        var_y = np.var(ys) if len(ys) > 1 else 0.0
        return float(var_x + var_y)

    def update(self, bbox_norm: list[float], confidence: float):
        self.bbox_norm = bbox_norm
        self.confidence = confidence
        self.last_seen = time.time()
        self.history.append(bbox_norm)
        if len(self.history) > 30:
            self.history.pop(0)
        self.disappeared_frames = 0


class ObjectTracker:
    def __init__(self, max_disappeared: int = 15, distance_threshold: float = 0.12):
        self.next_track_id = 1
        self.tracked_objects: dict[int, TrackedObject] = {}
        self.max_disappeared = max_disappeared
        self.distance_threshold = distance_threshold

    def update(self, detections: list[dict]) -> list[TrackedObject]:
        """
        Update tracking state with new frame detections.
        """
        # Phone & Person detections
        phone_detections = [d for d in detections if d["class_name"] == "cell phone"]

        if len(phone_detections) == 0:
            # Mark disappeared
            to_delete = []
            for tid, obj in self.tracked_objects.items():
                obj.disappeared_frames += 1
                if obj.disappeared_frames > self.max_disappeared:
                    to_delete.append(tid)
            for tid in to_delete:
                del self.tracked_objects[tid]
            return list(self.tracked_objects.values())

        # Match existing tracked objects with new detections
        current_ids = list(self.tracked_objects.keys())
        current_objects = list(self.tracked_objects.values())

        matched_det_indices = set()

        for tid, obj in list(self.tracked_objects.items()):
            obj_cx, obj_cy = obj.centroid
            best_dist = float("inf")
            best_det_idx = -1

            for idx, det in enumerate(phone_detections):
                if idx in matched_det_indices:
                    continue
                nx1, ny1, nx2, ny2 = det["bbox_norm"]
                det_cx, det_cy = (nx1 + nx2) / 2.0, (ny1 + ny2) / 2.0

                dist = math.hypot(det_cx - obj_cx, det_cy - obj_cy)
                if dist < best_dist and dist < self.distance_threshold:
                    best_dist = dist
                    best_det_idx = idx

            if best_det_idx != -1:
                det = phone_detections[best_det_idx]
                obj.update(det["bbox_norm"], det["confidence"])
                matched_det_indices.add(best_det_idx)
            else:
                obj.disappeared_frames += 1

        # Register new detections
        for idx, det in enumerate(phone_detections):
            if idx not in matched_det_indices:
                new_obj = TrackedObject(
                    track_id=self.next_track_id,
                    bbox_norm=det["bbox_norm"],
                    class_name=det["class_name"],
                    confidence=det["confidence"]
                )
                self.tracked_objects[self.next_track_id] = new_obj
                self.next_track_id += 1

        # Clean up expired tracks
        to_delete = [tid for tid, obj in self.tracked_objects.items() if obj.disappeared_frames > self.max_disappeared]
        for tid in to_delete:
            del self.tracked_objects[tid]

        return list(self.tracked_objects.values())
