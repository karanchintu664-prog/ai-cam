import os
import cv2
import time
import logging
from backend.app.models import AlertModel, SeatModel
from backend.app.config import settings

logger = logging.getLogger("AlertEngine")

class AlertEngine:
    """
    Evaluates suspicion scores, deduplicates seat incidents, stores thumbnail snapshots,
    and dispatches live staff alert payloads.
    """

    def __init__(self, cooldown_seconds: float = 8.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_seat_alert_time: dict[str, float] = {}

    def process_analysis(self, analysis: dict, frame=None) -> dict | None:
        """
        Process single behavior analysis record. Returns created Alert dict if triggered, else None.
        """
        if not analysis.get("is_suspicious"):
            return None

        seat_label = analysis.get("seat_label", "Unmapped")
        if seat_label.startswith("Seat "):
            seat_id = seat_label.replace("Seat ", "")
        else:
            seat_id = seat_label

        now = time.time()
        last_time = self.last_seat_alert_time.get(seat_id, 0)

        # Cooldown check to prevent duplicate alert spam for the same ongoing incident
        if now - last_time < self.cooldown_seconds:
            return None

        self.last_seat_alert_time[seat_id] = now

        # Save Thumbnail Snapshot
        thumbnail_url = ""
        if frame is not None and frame.size > 0:
            filename = f"snapshot_{seat_id}_{int(now)}.jpg"
            filepath = os.path.join(settings.THUMBNAIL_DIR, filename)
            try:
                # Resize for lightweight storage
                thumb = cv2.resize(frame, (480, 270))
                cv2.imwrite(filepath, thumb)
                thumbnail_url = f"/static/thumbnails/{filename}"
            except Exception as e:
                logger.error(f"Failed to save thumbnail: {e}")

        # Save to Database
        alert_record = AlertModel.create_alert(
            seat_id=seat_id,
            score=analysis["suspicion_score"],
            duration=analysis["duration_seconds"],
            confidence=analysis["confidence"],
            reason=analysis["analytical_reason"],
            thumbnail_url=thumbnail_url
        )

        # Update Seat status in DB
        SeatModel.update_seat_status(seat_id, "suspicious_alert")

        logger.info(f"ALERT TRIGGERED: {seat_id} - Score: {analysis['suspicion_score']}%")
        return alert_record
