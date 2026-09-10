import pytest
from pathlib import Path
from backend.app.video.reader import VideoReader

SAMPLE_VIDEO_PATH = Path("sample_data/benchmark_sample.mp4")

def test_video_metadata():
    assert SAMPLE_VIDEO_PATH.exists(), "Sample video should exist."
    reader = VideoReader(SAMPLE_VIDEO_PATH)
    meta = reader.get_metadata()

    assert meta.filename == "benchmark_sample.mp4"
    assert meta.width == 640
    assert meta.height == 360
    assert abs(meta.fps - 30.0) < 1.0
    assert meta.total_frames == 300
    assert abs(meta.duration_seconds - 10.0) < 0.5
    assert meta.file_size_bytes > 0

def test_video_frame_generator():
    reader = VideoReader(SAMPLE_VIDEO_PATH)
    frames = list(reader.iter_frames(downsample_size=(80, 45), grayscale=True))
    assert len(frames) == 300
    idx, ts, frame = frames[0]
    assert idx == 0
    assert ts == 0.0
    assert frame.shape == (45, 80)

def test_extract_single_frame():
    reader = VideoReader(SAMPLE_VIDEO_PATH)
    rgb_frame = reader.extract_frame_at(10)
    assert rgb_frame is not None
    assert rgb_frame.shape == (360, 640, 3)

def test_nonexistent_video():
    with pytest.raises(FileNotFoundError):
        VideoReader("non_existent_file.mp4")
