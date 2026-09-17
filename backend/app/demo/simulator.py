import cv2
import numpy as np
import time
import math

class CinemaTheatreSimulator:
    """
    Simulates a live camera feed of a cinema theater audience hall.
    Generates video frames with interactive simulation scenarios for demonstration.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.frame_count = 0
        self.active_scenario = "recording_attempt"  # "normal", "casual_phone", "recording_attempt"
        self.seats_config = self._init_seats()

    def _init_seats(self) -> list[dict]:
        rows = ["A", "B", "C", "D"]
        cols = 14
        seats = []
        for r_idx, r_label in enumerate(rows):
            y1 = int(self.height * (0.25 + r_idx * 0.17))
            y2 = y1 + int(self.height * 0.13)
            for c_idx in range(1, cols + 1):
                x1 = int(self.width * (0.04 + (c_idx - 1) * 0.066))
                x2 = x1 + int(self.width * 0.058)
                seats.append({
                    "seat_id": f"{r_label}{c_idx}",
                    "row": r_label,
                    "col": c_idx,
                    "bbox": [x1, y1, x2, y2],
                    "center": [(x1 + x2) // 2, (y1 + y2) // 2]
                })
        return seats

    def set_scenario(self, scenario_name: str):
        self.active_scenario = scenario_name
        self.frame_count = 0

    def generate_frame(self) -> np.ndarray:
        self.frame_count += 1
        t = self.frame_count * 0.05

        # 1. Dark Cinema Audience Environment Background
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (12, 16, 24)  # Deep ambient dark blue/gray

        # 2. Render Cinema Screen at top with dynamic light projection
        screen_h = int(self.height * 0.14)
        cv2.rectangle(frame, (100, 10), (self.width - 100, screen_h), (220, 220, 240), -1)
        
        # Moving screen content light simulation
        glow_x = int(self.width / 2 + math.sin(t * 2) * 300)
        cv2.circle(frame, (glow_x, screen_h // 2), 60, (255, 200, 150), -1)
        cv2.putText(frame, "MOVIE SCREEN - NOW PLAYING", (self.width // 2 - 180, screen_h // 2 + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 60), 2)

        # Ambient screen light cone over theater seating area
        overlay = frame.copy()
        pts = np.array([[100, screen_h], [self.width - 100, screen_h], [self.width, self.height], [0, self.height]])
        cv2.fillPoly(overlay, [pts], (40, 45, 65))
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

        # 3. Draw Theater Seats & Audience Silhouettes
        for seat in self.seats_config:
            x1, y1, x2, y2 = seat["bbox"]
            s_id = seat["seat_id"]

            # Seat Chair frame
            cv2.rectangle(frame, (x1, y1), (x2, y2), (35, 42, 58), 2)

            # Person Silhouette
            head_center = (seat["center"][0], y1 + 25)
            cv2.circle(frame, head_center, 14, (55, 65, 85), -1)
            cv2.ellipse(frame, (seat["center"][0], y1 + 65), (22, 28), 0, 180, 360, (55, 65, 85), -1)

            # Seat Number Tag
            cv2.putText(frame, s_id, (x1 + 4, y2 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 135, 160), 1)

        # 4. Inject Interactive Scenario Phone Activity
        if self.active_scenario == "casual_phone":
            # Brief casual phone check at Seat B4 between frames 30..70 (approx 1.5s)
            if 30 <= (self.frame_count % 150) <= 70:
                seat_b4 = next((s for s in self.seats_config if s["seat_id"] == "B4"), self.seats_config[0])
                cx, cy = seat_b4["center"]
                # Phone rectangle (casual low angle)
                cv2.rectangle(frame, (cx - 10, cy + 10), (cx + 10, cy + 25), (255, 255, 255), -1)
                cv2.rectangle(frame, (cx - 12, cy + 8), (cx + 12, cy + 27), (200, 200, 200), 1)

        elif self.active_scenario == "recording_attempt":
            # Suspicious filming attempt at Seat C14 (continuous upright phone pointing at screen)
            if self.frame_count >= 20:
                seat_c14 = next((s for s in self.seats_config if s["seat_id"] == "C14"), self.seats_config[-1])
                cx, cy = seat_c14["center"]
                
                # Phone held high facing screen (Bright glowing screen)
                phone_x1 = cx - 12 + int(math.sin(t * 3) * 1)  # Steady holding
                phone_y1 = cy - 15
                phone_x2 = phone_x1 + 24
                phone_y2 = phone_y1 + 42

                # Glowing white screen facing camera/screen
                cv2.rectangle(frame, (phone_x1, phone_y1), (phone_x2, phone_y2), (255, 255, 255), -1)
                # Outer smartphone body
                cv2.rectangle(frame, (phone_x1 - 2, phone_y1 - 2), (phone_x2 + 2, phone_y2 + 2), (180, 180, 180), 2)
                
                # Lens light reflection
                cv2.circle(frame, (phone_x1 + 6, phone_y1 + 6), 3, (0, 255, 255), -1)

        # Time HUD
        time_str = time.strftime("%H:%M:%S") + f" | SCENARIO: {self.active_scenario.upper()}"
        cv2.putText(frame, f"CINEMA HALL CAM-01 | {time_str}", (20, self.height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 1)

        return frame
