import os
import sys

# Ensure project root is on sys.path for backend package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2
import numpy as np
import json
import asyncio
import logging
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.models import AlertModel, SeatModel
from backend.app.vision.detector import ObjectDetectionEngine
from backend.app.vision.tracker import ObjectTracker
from backend.app.vision.seat_mapper import SeatMapper
from backend.app.vision.behavior_analyzer import BehaviorAnalyzer
from backend.app.vision.alert_engine import AlertEngine
from backend.app.demo.simulator import CinemaTheatreSimulator

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CinemaAntiPiracyApp")

# Initialize Database
init_db()

from contextlib import asynccontextmanager

# Global reference to main event loop for thread-safe async dispatch
main_loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    logger.info("System Initialized. Anti-Piracy Monitoring Active.")
    yield
    logger.info("System Shutting Down.")

# Initialize App
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Academic Anti-Piracy Real-Time Computer Vision & Staff Monitoring Alert System",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets
static_path = os.path.join(settings.BASE_DIR, "static")
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Vision Pipeline Modules Singleton Instances
detector = ObjectDetectionEngine()
tracker = ObjectTracker()
seat_mapper = SeatMapper()
behavior_analyzer = BehaviorAnalyzer()
alert_engine = AlertEngine()
simulator = CinemaTheatreSimulator()

# Active Video Feed Mode
feed_mode = "simulator"  # "simulator", "webcam", "file", "phone_camera"
custom_video_path = None
latest_custom_frame = None

# Connected WebSockets
active_websockets: List[WebSocket] = []

class StatusUpdatePayload(BaseModel):
    status: str

# WebSocket Connection Manager
async def broadcast_alert(alert_data: dict):
    for ws in list(active_websockets):
        try:
            await ws.send_json(alert_data)
        except Exception as e:
            logger.warning(f"WebSocket send failed: {e}")
            active_websockets.remove(ws)

@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"Staff Dashboard WebSocket client connected. Total clients: {len(active_websockets)}")
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        logger.info("WebSocket client disconnected.")

@app.websocket("/ws/stream_input")
async def websocket_stream_input_endpoint(websocket: WebSocket):
    global latest_custom_frame, feed_mode
    await websocket.accept()
    feed_mode = "phone_camera"
    logger.info("Mobile / Web Camera Streamer connected over WebSocket.")
    try:
        while True:
            data = await websocket.receive_bytes()
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None and frame.size > 0:
                latest_custom_frame = frame
    except WebSocketDisconnect:
        logger.info("Camera Streamer disconnected.")

import threading
import time

class WebcamStreamManager:
    """
    Thread-safe Singleton Webcam Stream Manager.
    Captures webcam frames in a background thread to eliminate hardware lock contention,
    preventing broken stream errors during browser reloads or mode switches.
    """
    def __init__(self):
        self.cap = None
        self.current_frame = None
        self.is_running = False
        self.lock = threading.Lock()
        self.thread = None
        self.device_index = 0

    def set_device_index(self, index: int):
        if self.device_index != index:
            self.device_index = index
            if self.is_running:
                self.stop()
                time.sleep(0.2)
                self.start()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        logger.info(f"Global Webcam Stream Manager thread started (device index {self.device_index}).")

    def _open_camera(self, idx: int):
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None and test_frame.size > 0:
                        return cap
                    cap.release()
            except Exception:
                pass
        return None

    def _update_loop(self):
        try:
            self.cap = self._open_camera(self.device_index)
            if self.cap is None or not self.cap.isOpened():
                logger.warning(f"Could not open webcam index {self.device_index}. Scanning fallback indices [0, 1, 2]...")
                for fallback_idx in [0, 1, 2]:
                    if fallback_idx == self.device_index:
                        continue
                    self.cap = self._open_camera(fallback_idx)
                    if self.cap is not None and self.cap.isOpened():
                        self.device_index = fallback_idx
                        logger.info(f"Successfully opened fallback webcam index {fallback_idx}.")
                        break

            if self.cap is not None and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                logger.info(f"Webcam hardware capture initialized successfully on device index {self.device_index}.")
        except Exception as e:
            logger.error(f"Failed to open webcam hardware: {e}")

        while self.is_running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    with self.lock:
                        self.current_frame = frame
                else:
                    time.sleep(0.02)
            else:
                time.sleep(0.05)
            time.sleep(0.02)

        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info("Webcam hardware capture released.")

    def get_frame(self):
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None

    def stop(self):
        self.is_running = False
        with self.lock:
            self.current_frame = None

webcam_manager = WebcamStreamManager()

# Video Feed Processing Generator
def generate_video_stream():
    global feed_mode, custom_video_path, latest_custom_frame
    
    file_cap = None

    while True:
        # Stop webcam thread if feed mode is not webcam
        if feed_mode != "webcam" and webcam_manager.is_running:
            webcam_manager.stop()

        frame = None
        if feed_mode == "phone_camera":
            if latest_custom_frame is not None:
                frame = latest_custom_frame.copy()
            else:
                frame = simulator.generate_frame()
        elif feed_mode == "webcam":
            if not webcam_manager.is_running:
                webcam_manager.start()
            frame = webcam_manager.get_frame()
            if frame is None and latest_custom_frame is not None:
                frame = latest_custom_frame.copy()
            if frame is None:
                frame = simulator.generate_frame()
        elif feed_mode == "simulator":
            frame = simulator.generate_frame()
        elif feed_mode == "file" and custom_video_path and os.path.exists(custom_video_path):
            if file_cap is None or not file_cap.isOpened():
                file_cap = cv2.VideoCapture(custom_video_path)
            ret, frame = file_cap.read()
            if not ret:
                file_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = file_cap.read()
            if not ret or frame is None:
                frame = simulator.generate_frame()
        else:
            frame = simulator.generate_frame()

        if frame is None:
            continue

        # 1. Run Object Detection
        detections = detector.detect(frame)

        # 2. Update Tracker
        tracked_phones = tracker.update(detections)

        # 3. Analyze Behavior & Map Seats
        current_frame_analysis = []
        active_seats_status = {}

        for phone_obj in tracked_phones:
            seat_dict = seat_mapper.map_bbox_to_seat(phone_obj.bbox_norm)
            seat_label = seat_mapper.format_seat_label(seat_dict)
            
            analysis = behavior_analyzer.analyze_tracked_phone(phone_obj, seat_label)
            current_frame_analysis.append(analysis)

            if seat_dict:
                s_id = seat_dict["seat_id"]
                if analysis["is_suspicious"]:
                    active_seats_status[s_id] = "suspicious_alert"
                else:
                    active_seats_status[s_id] = "phone_detected"

            # 4. Trigger Alert Engine
            alert_record = alert_engine.process_analysis(analysis, frame)
            if alert_record:
                # Async broadcast via main event loop safely
                if main_loop is not None and main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(broadcast_alert(alert_record), main_loop)

        # 5. Draw Visual Bounding Boxes & HUD Overlays
        h, w = frame.shape[:2]

        # Draw Seats Grid Outline
        for seat in seat_mapper.seats:
            sx1, sy1, sx2, sy2 = int(seat["x_min"] * w), int(seat["y_min"] * h), int(seat["x_max"] * w), int(seat["y_max"] * h)
            st = active_seats_status.get(seat["seat_id"], "normal")

            if st == "suspicious_alert":
                color = (0, 0, 255)  # Red
                thickness = 2
            elif st == "phone_detected":
                color = (0, 215, 255)  # Amber
                thickness = 2
            else:
                color = (50, 70, 90)  # Dim Blue/Gray
                thickness = 1

            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), color, thickness)

        # Draw Phone Bounding Boxes & Suspicion HUD
        for analysis in current_frame_analysis:
            phone_track = next((t for t in tracked_phones if t.track_id == analysis["track_id"]), None)
            if not phone_track:
                continue

            x1, y1, x2, y2 = [int(v * w if idx % 2 == 0 else v * h) for idx, v in enumerate(phone_track.bbox_norm)]
            score = analysis["suspicion_score"]
            seat = analysis["seat_label"]

            box_color = (0, 0, 255) if score >= 70.0 else (0, 215, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            label = f"{seat} | Suspicion: {score}% ({analysis['duration_seconds']}s)"
            cv2.rectangle(frame, (x1, y1 - 24), (x1 + len(label) * 9, y1), box_color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Encode Frame to JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        
        # Pacing stream rate at ~25 FPS to prevent socket buffer overflow
        time.sleep(0.04)

# REST API Endpoints

@app.get("/")
def read_root():
    return HTMLResponse(open(os.path.join(static_path, "index.html"), encoding="utf-8").read())

@app.get("/camera")
def read_camera():
    return HTMLResponse(open(os.path.join(static_path, "camera.html"), encoding="utf-8").read())

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")

class SeatCreatePayload(BaseModel):
    seat_id: str
    row_label: str
    seat_number: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float

class SeatConfigurePayload(BaseModel):
    rows: List[str]
    seats_per_row: int

@app.get("/api/seats")
def get_seats():
    return SeatModel.get_all_seats()

@app.post("/api/seats")
def add_or_update_seat(payload: SeatCreatePayload):
    SeatModel.add_seat(
        payload.seat_id, payload.row_label, payload.seat_number,
        payload.x_min, payload.y_min, payload.x_max, payload.y_max
    )
    seat_mapper.reload_seats()
    return {"status": "success", "seat_id": payload.seat_id}

@app.delete("/api/seats/{seat_id}")
def delete_seat(seat_id: str):
    SeatModel.delete_seat(seat_id)
    seat_mapper.reload_seats()
    return {"status": "success", "deleted_seat_id": seat_id}

@app.post("/api/seats/configure")
def configure_seats(payload: SeatConfigurePayload):
    if not payload.rows or payload.seats_per_row <= 0:
        raise HTTPException(status_code=400, detail="Invalid rows or seats_per_row configuration")
    SeatModel.configure_seats(payload.rows, payload.seats_per_row)
    seat_mapper.reload_seats()
    return {"status": "success", "total_seats": len(payload.rows) * payload.seats_per_row}

@app.get("/api/alerts")
def get_alerts(limit: int = 50):
    return AlertModel.get_all_alerts(limit=limit)

@app.patch("/api/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, payload: StatusUpdatePayload):
    valid_statuses = ["Requires Staff Verification", "Reviewed", "False Alarm", "Confirmed Suspicious"]
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")
    
    success = AlertModel.update_alert_status(alert_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "alert_id": alert_id, "new_status": payload.status}

@app.get("/api/stats")
def get_stats():
    stats = AlertModel.get_stats()
    stats["feed_mode"] = feed_mode
    stats["active_scenario"] = simulator.active_scenario
    stats["system_status"] = "ACTIVE & MONITORING"
    
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    stats["local_ip"] = local_ip
    stats["camera_url"] = f"http://{local_ip}:8000/static/camera.html"
    return stats

@app.post("/api/simulator/scenario")
def set_scenario(scenario_name: str = Form(...)):
    global feed_mode
    feed_mode = "simulator"
    valid_scenarios = ["normal", "casual_phone", "recording_attempt"]
    if scenario_name not in valid_scenarios:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Choose from {valid_scenarios}")
    simulator.set_scenario(scenario_name)
    SeatModel.reset_all_statuses()
    return {"status": "success", "scenario": scenario_name}

@app.get("/api/system_info")
def get_system_info():
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return {
        "local_ip": local_ip,
        "port": 8000,
        "camera_url": f"http://{local_ip}:8000/camera"
    }

@app.post("/api/mode")
def set_mode(mode: str = Form(...)):
    global feed_mode, latest_custom_frame
    if mode in ["simulator", "webcam", "file", "phone_camera"]:
        feed_mode = mode
        if mode != "phone_camera":
            latest_custom_frame = None  # Clear previous phone custom frame so webcam/simulator works cleanly!
        SeatModel.reset_all_statuses()
        return {"status": "success", "mode": mode}
    raise HTTPException(status_code=400, detail="Invalid mode")

@app.post("/api/webcam/index")
def set_webcam_index(index: int = Form(...)):
    webcam_manager.set_device_index(index)
    return {"status": "success", "camera_index": index}

@app.post("/api/upload_frame")
async def upload_frame(file: UploadFile = File(...)):
    global feed_mode, latest_custom_frame
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is not None and frame.size > 0:
        latest_custom_frame = frame
        feed_mode = "phone_camera"
        return {"status": "success", "mode": "phone_camera", "message": "Frame received successfully"}
    raise HTTPException(status_code=400, detail="Invalid image frame")

@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    global feed_mode, custom_video_path
    uploads_dir = os.path.join(settings.BASE_DIR, "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    custom_video_path = file_path
    feed_mode = "file"
    SeatModel.reset_all_statuses()
    return {"status": "success", "mode": "file", "filename": file.filename, "path": file_path}

if __name__ == "__main__":
    import uvicorn
    if getattr(sys, "frozen", False):
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

