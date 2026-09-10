from dataclasses import dataclass
import cv2
import numpy as np

@dataclass
class MotionMetrics:
    motion_score: float         # [0.0, 1.0] normalized motion magnitude
    is_scene_cut: bool          # True if sudden visual transition detected
    flow_magnitude: float       # Average optical flow vector length

def compute_motion_energy(prev_gray: np.ndarray, curr_gray: np.ndarray) -> MotionMetrics:
    """
    Computes motion magnitude and scene-cut flag between two grayscale frames.
    Uses Farneback optical flow on downsampled frames for fast, dense motion estimation.
    """
    if prev_gray.shape != curr_gray.shape:
        curr_gray = cv2.resize(curr_gray, (prev_gray.shape[1], prev_gray.shape[0]))

    # Compute dense optical flow
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.1,
        flags=0
    )

    # Magnitude of flow vectors (dx^2 + dy^2)
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    mean_mag = float(np.mean(mag))

    # Direct pixel difference
    diff = float(np.mean(cv2.absdiff(prev_gray, curr_gray))) / 255.0

    # Normalize motion score roughly to [0.0, 1.0] (saturation around flow mag of 5.0)
    norm_motion = min(1.0, mean_mag / 5.0)

    # Scene cut condition: significant visual difference or flow surge
    is_cut = (diff > 0.20) or (mean_mag > 8.0)

    return MotionMetrics(
        motion_score=round(norm_motion, 4),
        is_scene_cut=is_cut,
        flow_magnitude=round(mean_mag, 4)
    )
