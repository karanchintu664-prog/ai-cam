from backend.app.vision.tracker import TrackedObject
from backend.app.config import settings

class BehaviorAnalyzer:
    """
    Multi-Factor Suspicion Scoring Engine.
    Prioritizes false-positive reduction by requiring continuous phone presence,
    stable camera orientation, and low motion variance before raising suspicion.
    """

    def __init__(self, alert_threshold: float = settings.SUSPICION_ALERT_THRESHOLD):
        self.alert_threshold = alert_threshold

    def analyze_tracked_phone(self, tracked_phone: TrackedObject, seat_label: str) -> dict:
        """
        Evaluates tracked phone behavior telemetry and computes dynamic Suspicion Score (0.0 - 100.0).
        Returns telemetry analysis dictionary.
        """
        duration = tracked_phone.duration_seconds
        bbox = tracked_phone.bbox_norm  # [x1, y1, x2, y2]
        w = max(0.001, bbox[2] - bbox[0])
        h = max(0.001, bbox[3] - bbox[1])
        aspect_ratio = h / w

        # Factor 1: Persistence Duration (40% Weight)
        # 0 - 1.0s = low, 1.0 - 3.0s = ramping (casual check), > 3.0s = high (filming)
        if duration < 1.0:
            duration_factor = (duration / 1.0) * 20.0
        elif duration < settings.MIN_SUSPICIOUS_DURATION_SEC:
            duration_factor = 20.0 + ((duration - 1.0) / (settings.MIN_SUSPICIOUS_DURATION_SEC - 1.0)) * 25.0
        else:
            duration_factor = min(100.0, 70.0 + ((duration - settings.MIN_SUSPICIOUS_DURATION_SEC) / 3.0) * 30.0)

        # Factor 2: Screen-Facing Orientation (25% Weight)
        # Recording stance: phone held upright portrait (ratio 1.2 - 2.6) or landscape (0.45 - 0.8)
        if 1.2 <= aspect_ratio <= 2.6 or 0.45 <= aspect_ratio <= 0.8:
            orientation_factor = 95.0
        else:
            orientation_factor = 45.0

        # Factor 3: Posture Stability / Low Variance (20% Weight)
        variance = tracked_phone.get_position_variance()
        if len(tracked_phone.history) < 3:
            stability_factor = 50.0  # Neutral initial stance until tracking history accumulates
        elif variance < 0.001:
            stability_factor = 100.0  # Exceptionally steady recording stance
        elif variance < 0.005:
            stability_factor = 75.0
        else:
            stability_factor = 30.0  # Phone moving around, casual usage

        # Factor 4: Model Confidence (15% Weight)
        confidence_factor = tracked_phone.confidence * 100.0

        # Weighted Suspicion Score Calculation
        score = (
            (duration_factor * 0.40) +
            (orientation_factor * 0.25) +
            (stability_factor * 0.20) +
            (confidence_factor * 0.15)
        )

        final_score = round(min(100.0, max(0.0, score)), 1)
        is_suspicious = final_score >= self.alert_threshold

        # Formulate human-readable analytical reason
        reason = self._build_analytical_reason(duration, aspect_ratio, variance, final_score)

        return {
            "track_id": tracked_phone.track_id,
            "seat_label": seat_label,
            "suspicion_score": final_score,
            "is_suspicious": is_suspicious,
            "duration_seconds": round(duration, 1),
            "confidence": tracked_phone.confidence,
            "aspect_ratio": round(aspect_ratio, 2),
            "motion_variance": round(variance, 5),
            "analytical_reason": reason
        }

    def _build_analytical_reason(self, duration: float, aspect_ratio: float, variance: float, score: float) -> str:
        if score >= 75.0:
            return f"Continuous screen-oriented phone usage ({round(duration, 1)}s) with stable recording posture."
        elif score >= 50.0:
            return f"Phone visible for {round(duration, 1)}s in seat zone. Monitoring persistence."
        else:
            return f"Transient phone detection ({round(duration, 1)}s). Normal audience activity."
