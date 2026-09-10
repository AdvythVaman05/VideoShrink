import numpy as np
from backend.app.analysis.similarity import compute_frame_difference, compute_similarity, compute_histogram_similarity
from backend.app.analysis.motion import compute_motion_energy
from backend.app.analysis.quality import compute_quality_metrics
from backend.app.analysis.failure import FailureAnalyzer

def test_similarity_identical_frames():
    f1 = np.ones((100, 100, 3), dtype=np.uint8) * 128
    f2 = f1.copy()

    assert compute_frame_difference(f1, f2) == 0.0
    assert compute_similarity(f1, f2) == 1.0

def test_similarity_different_frames():
    f1 = np.zeros((100, 100, 3), dtype=np.uint8)
    f2 = np.ones((100, 100, 3), dtype=np.uint8) * 255

    assert compute_frame_difference(f1, f2) == 1.0
    assert compute_similarity(f1, f2) == 0.0

def test_motion_energy():
    f1 = np.zeros((90, 160), dtype=np.uint8)
    f2 = np.zeros((90, 160), dtype=np.uint8)
    # Draw a shifted circle
    import cv2
    cv2.circle(f1, (50, 45), 20, 255, -1)
    cv2.circle(f2, (80, 45), 20, 255, -1)

    motion = compute_motion_energy(f1, f2)
    assert motion.flow_magnitude > 0.0
    assert motion.motion_score > 0.0

def test_quality_metrics():
    # Sharp texture
    sharp = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    # Blurred smooth frame
    smooth = np.ones((100, 100), dtype=np.uint8) * 120

    q_sharp = compute_quality_metrics(sharp)
    q_smooth = compute_quality_metrics(smooth)

    assert q_sharp.blur_score > q_smooth.blur_score
    assert q_smooth.is_blurry is True

def test_failure_analyzer():
    analyzer = FailureAnalyzer()
    dummy_timeline = [
        {"timestamp": 1.0, "motion_score": 0.1, "is_scene_cut": False, "is_blurry": False},
        {"timestamp": 2.0, "motion_score": 0.1, "is_scene_cut": False, "is_blurry": False},
        # High motion surge between 6.0 and 7.5s
        {"timestamp": 6.0, "motion_score": 0.8, "is_scene_cut": True, "is_blurry": False},
        {"timestamp": 6.5, "motion_score": 0.7, "is_scene_cut": False, "is_blurry": False},
        {"timestamp": 7.0, "motion_score": 0.65, "is_scene_cut": False, "is_blurry": False},
        {"timestamp": 9.0, "motion_score": 0.05, "is_scene_cut": False, "is_blurry": False},
    ]

    segments = analyzer.analyze_timeline(dummy_timeline)
    assert len(segments) > 0
    seg = segments[0]
    assert seg.start_sec >= 5.5
    assert seg.severity == "high"
    assert any("scene" in r.lower() or "motion" in r.lower() for r in seg.reasons)
