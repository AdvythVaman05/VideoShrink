import sys
from pathlib import Path

# Add project root
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.video.reader import VideoReader
from backend.app.video.writer import VideoWriter
from backend.app.sampling.selector import FrameSelector
from backend.app.evaluation.benchmark import VisualPreservationProxyEvaluator
from backend.app.analysis.failure import FailureAnalyzer
from backend.app.evaluation.metrics import ReductionMetrics
from backend.app.db.database import db

def run_end_to_end_verification():
    sample_path = BASE_DIR / "sample_data" / "benchmark_sample.mp4"
    assert sample_path.exists(), "Sample video must exist."
    print("=== STEP 1: Video Input & Metadata Extraction ===")
    reader = VideoReader(sample_path)
    meta = reader.get_metadata()
    print(f"File: {meta.filename}, Resolution: {meta.width}x{meta.height}, FPS: {meta.fps}, Frames: {meta.total_frames}, Size: {meta.file_size_mb} MB")
    assert meta.total_frames == 300
    assert meta.width == 640
    assert meta.height == 360

    print("\n=== STEP 2: Intelligent Motion-Aware Sampling ===")
    selection = FrameSelector.run_selection(
        "motion_aware",
        reader,
        {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0, "scene_cut_threshold": 0.35}
    )
    print(f"Strategy: {selection.strategy_name}")
    print(f"Total Frames: {selection.total_frames}")
    print(f"Selected Frames: {selection.selected_count}")
    print(f"Reduction Rate: {selection.reduction_rate * 100:.1f}%")
    print(f"Retention Rate: {selection.retention_rate * 100:.1f}%")
    print(f"Effective FPS: {selection.effective_fps:.1f} FPS")
    print(f"Processing Time: {selection.processing_time_sec:.2f}s")
    assert selection.selected_count < selection.total_frames
    assert 0 in selection.selected_indices
    assert 299 in selection.selected_indices

    print("\n=== STEP 3: MP4 Reconstruction (FFmpeg / OpenCV) ===")
    writer = VideoWriter()
    out_file = BASE_DIR / "data" / "processed" / "e2e_verified_output.mp4"
    written_path = writer.write_selected_frames(
        source_video_path=sample_path,
        selected_indices=selection.selected_indices,
        output_video_path=out_file,
        preserve_duration=True
    )
    assert written_path.exists(), "Optimized MP4 must be created on disk."
    out_size = written_path.stat().st_size
    print(f"Reconstructed Output Video: {written_path} ({out_size / (1024*1024):.2f} MB)")
    assert out_size > 0, "Output video must not be empty."

    # Verify generated video readability with reader
    out_reader = VideoReader(written_path)
    out_meta = out_reader.get_metadata()
    print(f"Optimized Video Metadata: {out_meta.width}x{out_meta.height}, {out_meta.fps:.1f} FPS, {out_meta.total_frames} frames")
    assert out_meta.width == 640
    assert out_meta.height == 360
    assert abs(out_meta.total_frames - selection.selected_count) <= 2, "Output video frame count matches selected count."

    print("\n=== STEP 4: Failure & Quality Analysis ===")
    timeline_summary = [
        {
            "timestamp": r.timestamp_sec,
            "motion_score": r.motion_score or 0.0,
            "is_scene_cut": r.is_scene_cut,
            "is_blurry": r.is_blurry,
            "is_underexposed": r.is_underexposed,
            "is_overexposed": r.is_overexposed
        }
        for r in selection.frame_records
    ]
    analyzer = FailureAnalyzer()
    sensitive_segments = analyzer.analyze_timeline(timeline_summary)
    print(f"Identified {len(sensitive_segments)} sensitive segments:")
    for s in sensitive_segments:
        print(f" - [{s.start_time_formatted} - {s.end_time_formatted}] ({s.severity}): {s.reasons}")

    print("\n=== STEP 5: Visual Proxy Preservation Metric ===")
    evaluator = VisualPreservationProxyEvaluator()
    proxy = evaluator.evaluate(reader, selection)
    print(f"Proxy Fidelity Score: {proxy.proxy_fidelity_score * 100:.1f}%")
    print(f"Motion Peak Coverage: {proxy.motion_coverage_score * 100:.1f}%")
    print(f"Temporal Coverage: {proxy.temporal_coverage_score * 100:.1f}%")
    print(f"Disclaimer: {proxy.disclaimer[:60]}...")

    print("\n=== STEP 6: Experiment Logging & JSON Export ===")
    exp_id = db.create_experiment(
        video_filename="e2e_verified.mp4",
        video_duration=meta.duration_seconds,
        strategy=selection.strategy_name,
        parameters=selection.parameters,
        original_frames=meta.total_frames,
        selected_frames=selection.selected_count,
        retention_rate=selection.retention_rate,
        reduction_rate=selection.reduction_rate,
        effective_fps=selection.effective_fps,
        original_size_bytes=meta.file_size_bytes,
        compressed_size_bytes=out_size,
        file_size_reduction_pct=round(((meta.file_size_bytes - out_size)/meta.file_size_bytes)*100, 2),
        processing_time_sec=selection.processing_time_sec,
        info_preservation_score=proxy.proxy_fidelity_score,
        output_video_path=str(written_path),
        failure_summary={"segments": [s.__dict__ for s in sensitive_segments]},
        quality_summary={"mean_blur_score": 120.0}
    )
    json_export = db.export_experiment_json(exp_id)
    assert json_export is not None
    print(f"Successfully logged experiment: {exp_id}")
    print("Exported JSON sample snippet:")
    print(json_export[:280] + "\n...")

    print("\n=== ALL PIPELINE STAGES VERIFIED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_end_to_end_verification()
