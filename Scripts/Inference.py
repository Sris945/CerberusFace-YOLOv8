from ultralytics import YOLO
import cv2
import numpy as np
import os
import time
import argparse

# ----------------------------------------
#  Argument Parser
# ----------------------------------------
parser = argparse.ArgumentParser(description="YOLOv8 Face Detection with Zoom and Save")
parser.add_argument("--source", type=str, default="0", help="Video path or webcam index (default=0)")
parser.add_argument("--mode", type=str, default="auto", choices=["auto", "click"], help="Zoom mode")
parser.add_argument("--save", action="store_true", help="Save cropped face images")
args = parser.parse_args()

# ----------------------------------------
#  Load YOLOv8 Model
# ----------------------------------------
model = YOLO("../Model/Long-Detect-Yolov8s/runs/train/face_v1.pt")  # Use your path to best.pt

# ----------------------------------------
#  Source Selection
# ----------------------------------------
source = int(args.source) if args.source.isdigit() else args.source
cap = cv2.VideoCapture(source)

# ----------------------------------------
#  Save Setup
# ----------------------------------------
mode = args.mode
save_crops = args.save
last_faces = []
selected_face = None
frame_id = 0
timestamp = lambda: int(time.time() * 1000)
save_path = "face_data"
if save_crops:
    os.makedirs(save_path, exist_ok=True)

# ----------------------------------------
#  Click Detection Setup
# ----------------------------------------
def click_event(event, x, y, flags, param):
    global selected_face
    if mode != "click":
        return
    for box in last_faces:
        x1, y1, x2, y2 = box
        if x1 <= x <= x2 and y1 <= y <= y2:
            selected_face = (x1, y1, x2, y2)
            break

cv2.namedWindow("Face Detection")
cv2.setMouseCallback("Face Detection", click_event)

# ----------------------------------------
#  Main Loop
# ----------------------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        print(" End of video or failed to read frame.")
        break

    frame_id += 1
    frame_display = frame.copy()
    results = model(frame)[0]
    last_faces = []

    # ----------------------------
    # Detection and Drawing
    # ----------------------------
    for idx, box in enumerate(results.boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = box.conf[0]
        confidence = float(conf)
        label = f"{confidence:.2f}"

        # Draw bounding box
        cv2.rectangle(frame_display, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Draw confidence score
        cv2.putText(
            frame_display, label, (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

        last_faces.append((x1, y1, x2, y2))

        # Auto-save each face
        if mode == "auto" and save_crops:
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size > 0:
                zoomed = cv2.resize(face_crop, (200, 200))
                filename = os.path.join(save_path, f"{timestamp()}_{frame_id}_{idx}.jpg")
                cv2.imwrite(filename, zoomed)

    # ----------------------------
    #  Zoom Mode Handling
    # ----------------------------
    if mode == "auto" and last_faces:
        face_crops = []
        for (x1, y1, x2, y2) in last_faces:
            face = frame[y1:y2, x1:x2]
            if face.size > 0:
                zoomed = cv2.resize(face, (200, 200))
                face_crops.append(zoomed)
        if face_crops:
            stacked = np.hstack(face_crops)
            cv2.imshow("Zoomed Faces", stacked)

    elif mode == "click" and selected_face:
        x1, y1, x2, y2 = selected_face
        face = frame[y1:y2, x1:x2]
        if face.size > 0:
            zoomed = cv2.resize(face, (300, 300))
            cv2.imshow("Zoomed Face", zoomed)
            if save_crops:
                filename = os.path.join(save_path, f"clicked_{timestamp()}_{frame_id}.jpg")
                cv2.imwrite(filename, zoomed)
            selected_face = None

    # ----------------------------
    #  Display Detection Frame
    # ----------------------------
    cv2.imshow("Face Detection", frame_display)

    # ----------------------------
    #  Controls
    # ----------------------------
    key = cv2.waitKey(30) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('a'):
        mode = "auto"
        selected_face = None
        print("[MODE] Auto Zoom Enabled")
    elif key == ord('c'):
        mode = "click"
        print("[MODE] Click-to-Zoom Enabled")

# ----------------------------------------
#  Cleanup
# ----------------------------------------
cap.release()
cv2.destroyAllWindows()
 