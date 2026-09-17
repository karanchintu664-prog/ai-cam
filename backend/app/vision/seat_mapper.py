import math
from backend.app.models import SeatModel

class SeatMapper:
    """
    2D Spatial Coordinate Mapping Engine.
    Maps detection bounding boxes to cinema seat IDs (e.g. 'A1', 'B12', 'C14').
    """

    def __init__(self):
        self.seats = []
        self.reload_seats()

    def reload_seats(self):
        self.seats = SeatModel.get_all_seats()

    def map_bbox_to_seat(self, bbox_norm: list[float]) -> dict | None:
        """
        Takes normalized bounding box [x1, y1, x2, y2] (0.0 to 1.0)
        and finds the corresponding or nearest theater seat.
        """
        if not self.seats:
            self.reload_seats()

        cx = (bbox_norm[0] + bbox_norm[2]) / 2.0
        cy = (bbox_norm[1] + bbox_norm[3]) / 2.0

        # Step 1: Direct Point-in-Rectangle match
        for seat in self.seats:
            if seat["x_min"] <= cx <= seat["x_max"] and seat["y_min"] <= cy <= seat["y_max"]:
                return seat

        # Step 2: Nearest Seat fallback (Euclidean Distance to Seat Center)
        best_seat = None
        min_dist = float("inf")

        for seat in self.seats:
            seat_cx = (seat["x_min"] + seat["x_max"]) / 2.0
            seat_cy = (seat["y_min"] + seat["y_max"]) / 2.0
            dist = math.hypot(cx - seat_cx, cy - seat_cy)

            if dist < min_dist and dist < 0.25:  # Maximum 25% screen radius tolerance
                min_dist = dist
                best_seat = seat

        return best_seat

    def auto_calibrate_custom_seats(self, person_detections: list[dict]):
        """
        Dynamically auto-detects seating layout based on detected audience persons in live camera stream.
        """
        if not person_detections:
            return

        dynamic_seats = []
        for idx, person in enumerate(person_detections[:20]):
            b = person["bbox_norm"]
            row_idx = min(3, int(b[1] * 4))
            row_label = ["A", "B", "C", "D"][row_idx]
            seat_num = idx + 1
            seat_id = f"{row_label}{seat_num}"

            # Expand bbox slightly for seat zone
            pad_x = max(0.04, (b[2] - b[0]) * 0.2)
            pad_y = max(0.04, (b[3] - b[1]) * 0.2)
            x_min = max(0.0, b[0] - pad_x)
            x_max = min(1.0, b[2] + pad_x)
            y_min = max(0.0, b[1] - pad_y)
            y_max = min(1.0, b[3] + pad_y)

            dynamic_seats.append({
                "seat_id": seat_id,
                "row_label": row_label,
                "seat_number": seat_num,
                "x_min": round(x_min, 3),
                "y_min": round(y_min, 3),
                "x_max": round(x_max, 3),
                "y_max": round(y_max, 3),
                "status": "normal"
            })

        if dynamic_seats:
            self.seats = dynamic_seats

    def format_seat_label(self, seat_dict: dict | None) -> str:
        if seat_dict:
            return f"Seat {seat_dict['seat_id']}"
        return "Unmapped Area"
