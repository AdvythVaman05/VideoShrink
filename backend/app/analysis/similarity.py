import cv2
import numpy as np

def compute_frame_difference(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Computes normalized absolute difference between two frames [0.0, 1.0].
    Higher value = more visually different.
    """
    if frame1.shape != frame2.shape:
        frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))

    # Ensure single channel grayscale
    if len(frame1.shape) == 3:
        g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    else:
        g1 = frame1

    if len(frame2.shape) == 3:
        g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    else:
        g2 = frame2

    diff = cv2.absdiff(g1, g2)
    norm_mean_diff = float(np.mean(diff)) / 255.0

    # Localized block peak difference (4x4 spatial grid)
    # Prevents small moving targets on static backgrounds from being swallowed by global mean
    h, w = diff.shape
    blocks = [
        float(np.mean(diff[r*h//4:(r+1)*h//4, c*w//4:(c+1)*w//4])) / 255.0
        for r in range(4) for c in range(4)
    ]
    max_block_diff = max(blocks) if blocks else norm_mean_diff

    # Composite difference: 70% global average + 30% peak local block
    comp_diff = 0.70 * norm_mean_diff + 0.30 * max_block_diff
    return round(comp_diff, 4)

def compute_similarity(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Computes perceptual similarity score [0.0, 1.0].
    1.0 = identical, 0.0 = completely different.
    """
    diff = compute_frame_difference(frame1, frame2)
    similarity = max(0.0, min(1.0, 1.0 - diff))
    return round(similarity, 4)

def compute_histogram_similarity(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Computes histogram correlation similarity between two frames [0.0, 1.0].
    """
    if len(frame1.shape) == 3:
        h1 = cv2.calcHist([frame1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        h2 = cv2.calcHist([frame2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    else:
        h1 = cv2.calcHist([frame1], [0], None, [32], [0, 256])
        h2 = cv2.calcHist([frame2], [0], None, [32], [0, 256])

    cv2.normalize(h1, h1, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(h2, h2, 0, 1, cv2.NORM_MINMAX)

    score = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
    # Correlation ranges from -1 to 1; normalize to [0, 1]
    norm_score = (score + 1.0) / 2.0
    return round(float(np.clip(norm_score, 0.0, 1.0)), 4)
