import os
import sys

class Settings:
    PROJECT_NAME: str = "AI-Based Cinema Theatre Anti-Piracy Monitoring and Alert System"
    VERSION: str = "1.0.0"
    ACADEMIC_GOAL: str = "Real-time non-intrusive mobile phone recording detection & staff alert system"

    # Privacy Guarantee Flags (Enforced System Constants)
    ENABLE_FACIAL_RECOGNITION: bool = False
    STORE_PERSONAL_DATA: bool = False

    # Detection & Analysis Thresholds
    DETECTION_CONF_THRESHOLD: float = 0.35
    SUSPICION_ALERT_THRESHOLD: float = 70.0  # Suspicion score percentage (0-100)
    MIN_SUSPICIOUS_DURATION_SEC: float = 3.0  # Minimum seconds phone visible to trigger alert

    # Seating Configuration
    DEFAULT_ROWS: list[str] = ["A", "B", "C", "D"]
    SEATS_PER_ROW: int = 14

    # Storage Paths
    if getattr(sys, 'frozen', False):
        MEIPASS_DIR: str = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        BASE_DIR: str = os.path.join(MEIPASS_DIR, "backend", "app")
        EXEC_DIR: str = os.path.dirname(sys.executable)
        DATABASE_PATH: str = os.path.join(EXEC_DIR, "cinema_antipiracy.db")
    else:
        BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
        DATABASE_PATH: str = os.path.join(os.path.dirname(BASE_DIR), "cinema_antipiracy.db")

    THUMBNAIL_DIR: str = os.path.join(BASE_DIR, "static", "thumbnails")

settings = Settings()
os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)

