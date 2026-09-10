import sys
from pathlib import Path
import cv2
import numpy as np

def generate_synthetic_video(
    output_path: str | Path = "sample_data/benchmark_sample.mp4",
    fps: int = 30,
    duration_sec: int = 10,
    width: int = 640,
    height: int = 360
) -> Path:
    """
    Generates a benchmark video containing:
    1. Static scene (frames 0 to 90 = 0-3s): completely unchanging background and graphic.
    2. Continuous large object motion (frames 90 to 180 = 3-6s): moving high-contrast rectangle across screen.
    3. Abrupt scene transition / cut (frame 180 = 6s): flips from dark slate to bright white/orange.
    4. High chaotic motion burst (frames 181 to 240 = 6-8s): multiple bouncing circles and flashing elements.
    5. Static cooldown (frames 240 to 300 = 8-10s): completely unchanging background.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(out_file), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {out_file}")

    total_frames = fps * duration_sec

    # Static frame 1
    static_frame_1 = np.zeros((height, width, 3), dtype=np.uint8)
    static_frame_1[:] = (35, 35, 45)  # Dark slate
    cv2.putText(static_frame_1, "SCENE 1: Static Video Dataset Baseline", (40, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    cv2.putText(static_frame_1, "Redundant Frames / Zero Motion", (40, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
    cv2.rectangle(static_frame_1, (240, 140), (400, 260), (0, 160, 220), -1)

    # Static frame 2 (cooldown)
    static_frame_2 = np.zeros((height, width, 3), dtype=np.uint8)
    static_frame_2[:] = (45, 35, 45)  # Purple slate
    cv2.putText(static_frame_2, "SCENE 4: Cooldown Static Segment", (40, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    cv2.putText(static_frame_2, "Redundant Static Content", (40, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
    cv2.rectangle(static_frame_2, (260, 150), (380, 230), (180, 100, 240), -1)

    for f in range(total_frames):
        ts = f / fps

        if ts < 3.0:
            # Segment 1: Pure static scene (0 to 3s)
            writer.write(static_frame_1)

        elif ts < 6.0:
            # Segment 2: Smooth linear motion (3 to 6s)
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (40, 45, 35)  # Olive slate
            cv2.putText(frame, "SCENE 2: Smooth Linear Object Motion", (40, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
            # Large moving block spanning significant visual area
            progress = (ts - 3.0) / 3.0
            bx = int(50 + progress * (width - 250))
            by = int(140 + 50 * np.sin(progress * 2 * np.pi))
            cv2.rectangle(frame, (bx, by), (bx + 140, by + 120), (50, 220, 100), -1)
            writer.write(frame)

        elif ts < 8.0:
            # Segment 3: Abrupt cut & high chaotic motion (6 to 8s)
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (230, 240, 250)  # Bright high-contrast cut!
            cv2.putText(frame, "SCENE 3: ABRUPT CUT & HIGH MOTION", (40, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 180), 2)

            t_sub = ts - 6.0
            for i in range(5):
                cx = int((width / 2) + 200 * np.cos(t_sub * 10 + i * 1.2))
                cy = int((height / 2) + 110 * np.sin(t_sub * 10 + i * 1.2))
                cv2.circle(frame, (cx, cy), 35 + i * 5, (20, 80 + i * 35, 220), -1)
            writer.write(frame)

        else:
            # Segment 4: Static cooldown (8 to 10s)
            writer.write(static_frame_2)

    writer.release()
    print(f"Generated synthetic benchmark video at: {out_file} ({total_frames} frames, {duration_sec}s)")
    return out_file

if __name__ == "__main__":
    generate_synthetic_video()
