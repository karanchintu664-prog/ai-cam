import uuid
from datetime import datetime
from backend.app.database import get_db_connection

class SeatModel:
    @staticmethod
    def get_all_seats():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM seats ORDER BY row_label, seat_number")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def add_seat(seat_id: str, row_label: str, seat_number: int, x_min: float, y_min: float, x_max: float, y_max: float):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO seats (seat_id, row_label, seat_number, x_min, y_min, x_max, y_max, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'normal')",
            (seat_id, row_label, seat_number, x_min, y_min, x_max, y_max)
        )
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete_seat(seat_id: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM seats WHERE seat_id = ?", (seat_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def configure_seats(rows_list: list[str], seats_per_row: int):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM seats")
        
        row_count = len(rows_list)
        for r_idx, r_label in enumerate(rows_list):
            y1 = 0.15 + (r_idx * (0.70 / max(1, row_count)))
            y2 = y1 + (0.60 / max(1, row_count))
            for c_idx in range(1, seats_per_row + 1):
                s_id = f"{r_label}{c_idx}"
                x1 = 0.04 + ((c_idx - 1) * (0.90 / max(1, seats_per_row)))
                x2 = x1 + (0.80 / max(1, seats_per_row))
                cursor.execute(
                    "INSERT INTO seats (seat_id, row_label, seat_number, x_min, y_min, x_max, y_max, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (s_id, r_label, c_idx, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), 'normal')
                )
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def update_seat_status(seat_id: str, status: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE seats SET status = ? WHERE seat_id = ?", (status, seat_id))
        conn.commit()
        conn.close()

    @staticmethod
    def reset_all_statuses():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE seats SET status = 'normal'")
        conn.commit()
        conn.close()

class AlertModel:
    @staticmethod
    def create_alert(seat_id: str, score: float, duration: float, confidence: float, reason: str, thumbnail_url: str = ""):
        conn = get_db_connection()
        cursor = conn.cursor()
        alert_uuid = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO alerts (alert_uuid, timestamp, seat_id, score, duration, confidence, reason, thumbnail_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (alert_uuid, timestamp, seat_id, score, duration, confidence, reason, thumbnail_url, 'Requires Staff Verification'))
        
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()

        return {
            "id": alert_id,
            "alert_uuid": alert_uuid,
            "timestamp": timestamp,
            "seat_id": seat_id,
            "score": score,
            "duration": duration,
            "confidence": confidence,
            "reason": reason,
            "thumbnail_url": thumbnail_url,
            "status": "Requires Staff Verification"
        }

    @staticmethod
    def get_all_alerts(limit: int = 50):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return alerts

    @staticmethod
    def update_alert_status(alert_id: int, new_status: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET status = ? WHERE id = ?", (new_status, alert_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_stats():
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM alerts")
        total_alerts = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as pending FROM alerts WHERE status = 'Requires Staff Verification'")
        pending_alerts = cursor.fetchone()['pending']

        cursor.execute("SELECT COUNT(*) as confirmed FROM alerts WHERE status = 'Confirmed Suspicious'")
        confirmed_alerts = cursor.fetchone()['confirmed']

        cursor.execute("SELECT COUNT(*) as false_alarms FROM alerts WHERE status = 'False Alarm'")
        false_alarms = cursor.fetchone()['false_alarms']

        conn.close()

        return {
            "total_alerts": total_alerts,
            "pending_alerts": pending_alerts,
            "confirmed_alerts": confirmed_alerts,
            "false_alarms": false_alarms
        }
