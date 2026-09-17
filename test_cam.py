import cv2
import sys

print("Testing OpenCV VideoCapture camera devices...")

for idx in [0, 1, 2]:
    print(f"\n--- Testing index {idx} ---")
    
    # Test DSHOW
    cap_dshow = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if cap_dshow.isOpened():
        ret, frame = cap_dshow.read()
        print(f"CAP_DSHOW idx {idx}: Opened = True, Read Ret = {ret}, Frame Shape = {frame.shape if ret and frame is not None else None}")
        cap_dshow.release()
    else:
        print(f"CAP_DSHOW idx {idx}: Opened = False")

    # Test MSMF / Default
    cap_def = cv2.VideoCapture(idx)
    if cap_def.isOpened():
        ret, frame = cap_def.read()
        print(f"DEFAULT idx {idx}: Opened = True, Read Ret = {ret}, Frame Shape = {frame.shape if ret and frame is not None else None}")
        cap_def.release()
    else:
        print(f"DEFAULT idx {idx}: Opened = False")

print("\nCamera test finished.")
