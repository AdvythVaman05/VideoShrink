import pytest
from pathlib import Path
from backend.app.video.reader import VideoReader
from backend.app.sampling.uniform import UniformSampler
from backend.app.sampling.perceptual import PerceptualSampler
from backend.app.sampling.motion_aware import MotionAwareSampler
from backend.app.sampling.selector import FrameSelector

SAMPLE_VIDEO_PATH = Path("sample_data/benchmark_sample.mp4")

@pytest.fixture
def video_reader():
    return VideoReader(SAMPLE_VIDEO_PATH)

def test_uniform_sampler(video_reader):
    sampler = UniformSampler(target_fps=10.0)
    result = sampler.sample(video_reader)

    assert result.strategy_name == "uniform"
    assert result.total_frames == 300
    # At 30 FPS to 10 FPS (stride 3), 300 / 3 = 100 frames selected (plus boundary edge)
    assert 98 <= result.selected_count <= 102
    assert result.retention_rate < 0.40
    assert result.reduction_rate > 0.60
    assert 0 in result.selected_indices
    assert 299 in result.selected_indices

def test_perceptual_sampler(video_reader):
    sampler = PerceptualSampler(similarity_threshold=0.96)
    result = sampler.sample(video_reader)

    assert result.strategy_name == "perceptual"
    assert result.total_frames == 300
    assert result.selected_count < result.total_frames
    assert 0 in result.selected_indices
    assert 299 in result.selected_indices

    # Verify that in the static section (frames 0-89), fewer frames are retained than in the moving section (frames 90-179)
    static_selected = sum(1 for idx in result.selected_indices if 0 <= idx < 90)
    moving_selected = sum(1 for idx in result.selected_indices if 90 <= idx < 180)
    assert moving_selected > static_selected, f"Expected moving ({moving_selected}) > static ({static_selected})"

def test_motion_aware_sampler(video_reader):
    sampler = MotionAwareSampler(motion_sensitivity=0.5, min_fps=2.0, max_fps=15.0)
    result = sampler.sample(video_reader)

    assert result.strategy_name == "motion_aware"
    assert result.total_frames == 300
    assert result.selected_count > 0
    assert result.selected_count < result.total_frames

    # High motion burst is in frames 180 to 240 (60 frames).
    # Cooldown static is 240 to 300 (60 frames).
    high_motion_selected = sum(1 for idx in result.selected_indices if 180 <= idx < 240)
    cooldown_selected = sum(1 for idx in result.selected_indices if 240 <= idx < 300)

    assert high_motion_selected > cooldown_selected, (
        f"Motion-aware should keep more frames in high-motion ({high_motion_selected}) "
        f"than in static cooldown ({cooldown_selected})"
    )

    # Check that scene cut around frame 180 was flagged
    scene_cuts = [r for r in result.frame_records if r.is_scene_cut]
    assert len(scene_cuts) > 0, "Scene transition around frame 180 should be detected"

def test_frame_selector_dispatch(video_reader):
    uniform = FrameSelector.get_sampler("uniform", {"target_fps": 5.0})
    assert isinstance(uniform, UniformSampler)

    perceptual = FrameSelector.get_sampler("perceptual", {"similarity_threshold": 0.85})
    assert isinstance(perceptual, PerceptualSampler)

    motion = FrameSelector.get_sampler("motion_aware", {"min_fps": 1.0})
    assert isinstance(motion, MotionAwareSampler)

    with pytest.raises(ValueError):
        FrameSelector.get_sampler("unknown_strategy")
