import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sqlite3
import json
from datetime import datetime
from backend.app.config import settings

def get_db_connection():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Seats Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seats (
            seat_id TEXT PRIMARY KEY,
            row_label TEXT NOT NULL,
            seat_number INTEGER NOT NULL,
            x_min REAL NOT NULL,
            y_min REAL NOT NULL,
            x_max REAL NOT NULL,
            y_max REAL NOT NULL,
            status TEXT DEFAULT 'normal'
        )
    ''')

    # Create Alerts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_uuid TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            seat_id TEXT NOT NULL,
            score REAL NOT NULL,
            duration REAL NOT NULL,
            confidence REAL NOT NULL,
            reason TEXT NOT NULL,
            thumbnail_url TEXT,
            status TEXT DEFAULT 'Requires Staff Verification',
            FOREIGN KEY (seat_id) REFERENCES seats (seat_id)
        )
    ''')

    # Create System Configs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configurations (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Populate or update Default Seats
    cursor.execute("SELECT COUNT(*) as cnt FROM seats WHERE x_max > 1.0 OR x_min > 0.95")
    overflow_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM seats")
    total_count = cursor.fetchone()['cnt']

    if total_count == 0 or overflow_count > 0:
        cursor.execute("DELETE FROM seats")
        rows = settings.DEFAULT_ROWS
        cols = settings.SEATS_PER_ROW
        for r_idx, r_label in enumerate(rows):
            y1 = 0.15 + (r_idx * 0.18)
            y2 = y1 + 0.14
            for c_idx in range(1, cols + 1):
                s_id = f"{r_label}{c_idx}"
                x1 = 0.04 + ((c_idx - 1) * 0.065)
                x2 = x1 + 0.058
                cursor.execute(
                    "INSERT INTO seats (seat_id, row_label, seat_number, x_min, y_min, x_max, y_max, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (s_id, r_label, c_idx, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3), 'normal')
                )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", settings.DATABASE_PATH)
