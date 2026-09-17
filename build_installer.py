import os
import sys
import shutil
import zipfile
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_APP_DIR = os.path.join(DESKTOP_DIR, "Cinema_Anti_Piracy_App")
ZIP_OUTPUT_PATH = os.path.join(DESKTOP_DIR, "Cinema_Anti_Piracy_Portable.zip")

print("--- AI Cinema Anti-Piracy Executable Build Script ---")
print(f"Project Root: {PROJECT_ROOT}")
print(f"Target Desktop App Dir: {OUTPUT_APP_DIR}")

# 1. PyInstaller command construction
pyinstaller_cmd = [
    sys.executable,
    "-m", "PyInstaller",
    "--name=CinemaAntiPiracy",
    "--noconfirm",
    "--clean",
    "--onedir",  # Folder distribution for fast startup & clean asset loading
    "--console", # Keep console visible so user sees server status
    f"--add-data={os.path.join(PROJECT_ROOT, 'backend', 'app', 'static')}{os.pathsep}{os.path.join('backend', 'app', 'static')}",
    os.path.join(PROJECT_ROOT, "backend", "app", "main.py")
]

print("Running PyInstaller...")
res = subprocess.run(pyinstaller_cmd, cwd=PROJECT_ROOT)
if res.returncode != 0:
    print("PyInstaller build failed!")
    sys.exit(1)

dist_built_dir = os.path.join(PROJECT_ROOT, "dist", "CinemaAntiPiracy")
print(f"Build succeeded at {dist_built_dir}")

# 2. Copy build output to Desktop
if os.path.exists(OUTPUT_APP_DIR):
    shutil.rmtree(OUTPUT_APP_DIR)

shutil.copytree(dist_built_dir, OUTPUT_APP_DIR)
print(f"Copied package to Desktop: {OUTPUT_APP_DIR}")

# 3. Create 1-Click Launcher Script (Start_Cinema_System.bat)
bat_content = """@echo off
title AI Cinema Anti-Piracy Monitoring System - @karanchintu664
cd /d "%~dp0"
echo =========================================================
echo    AI Cinema Anti-Piracy Monitoring & Alert System
echo    Developed by Instagram: @karanchintu664
echo =========================================================
echo.
echo Starting backend server on http://127.0.0.1:8000...
echo Opening browser dashboard in 3 seconds...
echo.

start "" "http://127.0.0.1:8000"

CinemaAntiPiracy.exe

pause
"""

bat_path = os.path.join(OUTPUT_APP_DIR, "Start_Cinema_System.bat")
with open(bat_path, "w", encoding="utf-8") as f:
    f.write(bat_content)

# Also create shortcut launcher on Desktop directly
desktop_bat_path = os.path.join(DESKTOP_DIR, "Start_Cinema_Anti_Piracy.bat")
desktop_bat_content = f"""@echo off
cd /d "{OUTPUT_APP_DIR}"
call Start_Cinema_System.bat
"""
with open(desktop_bat_path, "w", encoding="utf-8") as f:
    f.write(desktop_bat_content)

# 4. Create README Transfer Instructions
readme_content = """========================================================================
 AI CINEMA THEATRE ANTI-PIRACY MONITORING SYSTEM - PORTABLE PACKAGE
 Developed by Instagram: @karanchintu664
========================================================================

HOW TO RUN ON THIS DEVICE:
1. Double-click "Start_Cinema_System.bat".
2. The server will start and automatically open http://127.0.0.1:8000 in your browser.

HOW TO TRANSFER AND RUN ON ANY OTHER WINDOWS DEVICE:
1. Copy the entire "Cinema_Anti_Piracy_App" folder (or the "Cinema_Anti_Piracy_Portable.zip" file) to a USB drive or transfer via network / Google Drive.
2. On the target computer, open the folder.
3. Double-click "Start_Cinema_System.bat".
4. NO Python, Git, or installation commands are required on the target computer!

FEATURES & ENDPOINTS:
- Staff Monitoring Dashboard: http://127.0.0.1:8000
- Mobile Phone Web-Cam Streamer: http://<local-ip>:8000/camera

========================================================================
"""
readme_path = os.path.join(OUTPUT_APP_DIR, "README_TRANSFER_INSTRUCTIONS.txt")
with open(readme_path, "w", encoding="utf-8") as f:
    f.write(readme_content)

# 5. Create Portable Zip File on Desktop
print(f"Creating portable zip archive at: {ZIP_OUTPUT_PATH}...")
if os.path.exists(ZIP_OUTPUT_PATH):
    os.remove(ZIP_OUTPUT_PATH)

with zipfile.ZipFile(ZIP_OUTPUT_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(OUTPUT_APP_DIR):
        for file in files:
            file_abs = os.path.join(root, file)
            rel_path = os.path.relpath(file_abs, os.path.dirname(OUTPUT_APP_DIR))
            zipf.write(file_abs, rel_path)

print("\nSUCCESS! Portable desktop package ready.")
print(f"1. Desktop Folder: {OUTPUT_APP_DIR}")
print(f"2. Desktop Shortcut: {desktop_bat_path}")
print(f"3. Portable Transfer Zip: {ZIP_OUTPUT_PATH}")
