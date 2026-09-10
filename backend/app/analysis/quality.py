from dataclasses import dataclass
import cv2
import numpy as np

@dataclass
class QualityMetrics:
    blur_score: float        # Variance of the Laplacian (higher = sharper, lower = blurrier)
    brightness: float        # Mean pixel intensity [0, 255]
    contrast: float          # Standard deviation of pixel intensity
    is_blurry: bool          # True if blur_score < blur_threshold
    is_underexposed: bool    # True if brightness < 25 (very dark)
    is_overexposed: bool     # True if brightness > 230 (very bright)

def compute_quality_metrics(
    frame: np.ndarray,
    blur_threshold: float = 100.0
) -> QualityMetrics:
    """
    Computes lightweight frame quality metrics on downsampled frame.
    """
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # Blur score via Laplacian variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Brightness (mean) and Contrast (standard deviation)
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))

    return QualityMetrics(
        blur_score=round(laplacian_var, 2),
        brightness=round(mean_val, 2),
        contrast=round(std_val, 2),
        is_blurry=(laplacian_var < blur_threshold),
        is_underexposed=(mean_val < 25.0),
        is_overexposed=(mean_val > 230.0)
    )
