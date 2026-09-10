import sys
import json
import time
import csv
from pathlib import Path
from typing import Dict, Any, List

# Add project root
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.video.reader import VideoReader
from backend.app.video.writer import VideoWriter
from backend.app.sampling.selector import FrameSelector
from backend.app.analysis.failure import FailureAnalyzer
from backend.app.evaluation.benchmark import VisualPreservationProxyEvaluator

TEST_VIDEOS_DIR = BASE_DIR / "experiments" / "test_videos"
RESULTS_DIR = BASE_DIR / "experiments" / "results"
OPTIMIZED_DIR = BASE_DIR / "experiments" / "optimized_videos"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)

STRATEGIES = [
    {
        "name": "uniform",
        "label": "Uniform Baseline",
        "params": {"target_fps": 10.0}
    },
    {
        "name": "perceptual",
        "label": "Perceptual Similarity",
        "params": {"similarity_threshold": 0.96, "max_interval_sec": 2.5}
    },
    {
        "name": "motion_aware",
        "label": "Motion-Aware Adaptive",
        "params": {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0, "scene_cut_threshold": 0.35}
    }
]

def run_validation():
    video_files = sorted(list(TEST_VIDEOS_DIR.glob("video_*.mp4")))
    if not video_files:
        print("No test videos found in experiments/test_videos/. Run download_real_videos.py first.")
        return

    writer = VideoWriter()
    evaluator = VisualPreservationProxyEvaluator()
    failure_analyzer = FailureAnalyzer()

    all_results: List[Dict[str, Any]] = []
    csv_rows: List[Dict[str, Any]] = []

    print("=" * 95)
    print("VIDEOSHRINK REAL-WORLD VALIDATION SUITE")
    print(f"Total Test Videos: {len(video_files)} | Total Configurations per Video: {len(STRATEGIES)}")
    print("=" * 95)

    for vid_path in video_files:
        video_id = vid_path.stem
        reader = VideoReader(vid_path)
        meta = reader.get_metadata()

        print(f"\nEvaluating: {vid_path.name}")
        print(f" - Resolution: {meta.width}x{meta.height} | Native FPS: {meta.fps} | Total Frames: {meta.total_frames} | Size: {meta.file_size_mb} MB")

        for strat in STRATEGIES:
            s_name = strat["name"]
            s_label = strat["label"]
            s_params = strat["params"]

            # Run Sampling
            t0 = time.time()
            selection = FrameSelector.run_selection(s_name, reader, s_params)
            elapsed = time.time() - t0
            throughput = round(meta.total_frames / elapsed, 1) if elapsed > 0 else 0.0

            # Reconstruct optimized MP4
            out_filename = f"{video_id}_{s_name}.mp4"
            out_path = OPTIMIZED_DIR / out_filename
            written = writer.write_selected_frames(
                source_video_path=vid_path,
                selected_indices=selection.selected_indices,
                output_video_path=out_path,
                preserve_duration=True
            )

            out_size_bytes = written.stat().st_size if written.exists() else 0
            out_size_mb = round(out_size_bytes / (1024 * 1024), 2)
            file_reduction_pct = round(((meta.file_size_bytes - out_size_bytes) / meta.file_size_bytes) * 100.0, 2) if meta.file_size_bytes > 0 else 0.0

            # Sensitive Segment Analysis
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
            sensitive_segments = failure_analyzer.analyze_timeline(timeline_summary)

            # Visual Preservation Proxy Metric
            proxy_result = evaluator.evaluate(reader, selection)

            record = {
                "video_id": video_id,
                "video_filename": vid_path.name,
                "strategy": s_name,
                "strategy_label": s_label,
                "parameters": s_params,
                "original_frames": meta.total_frames,
                "selected_frames": selection.selected_count,
                "frame_retention_pct": round(selection.retention_rate * 100.0, 2),
                "frame_reduction_pct": round(selection.reduction_rate * 100.0, 2),
                "original_fps": meta.fps,
                "effective_output_fps": round(selection.effective_fps, 2),
                "original_size_bytes": meta.file_size_bytes,
                "original_size_mb": meta.file_size_mb,
                "optimized_size_bytes": out_size_bytes,
                "optimized_size_mb": out_size_mb,
                "actual_file_size_reduction_pct": file_reduction_pct,
                "processing_time_sec": round(selection.processing_time_sec, 2),
                "processing_throughput_fps": throughput,
                "sensitive_segments_count": len(sensitive_segments),
                "sensitive_segments": [s.__dict__ for s in sensitive_segments],
                "visual_preservation_proxy_score": proxy_result.proxy_fidelity_score,
                "motion_coverage_score": proxy_result.motion_coverage_score,
                "temporal_coverage_score": proxy_result.temporal_coverage_score,
                "sharpness_preservation_ratio": proxy_result.sharpness_preservation_ratio,
                "metric_label": "Visual/Data Preservation Proxy (Heuristic)",
            }
            all_results.append(record)

            csv_rows.append({
                "Video": vid_path.name,
                "Strategy": s_name,
                "Original Frames": meta.total_frames,
                "Selected Frames": selection.selected_count,
                "Frame Reduction %": f"{selection.reduction_rate * 100.0:.1f}%",
                "Frame Retention %": f"{selection.retention_rate * 100.0:.1f}%",
                "Effective FPS": f"{selection.effective_fps:.1f}",
                "Original Size (MB)": meta.file_size_mb,
                "Optimized Size (MB)": out_size_mb,
                "File Size Reduction %": f"{file_reduction_pct:.1f}%",
                "Processing Time (s)": f"{selection.processing_time_sec:.2f}",
                "Throughput (FPS)": f"{throughput:.1f}",
                "Sensitive Segments": len(sensitive_segments),
                "Proxy Score": f"{proxy_result.proxy_fidelity_score:.2f}",
            })

            print(f"  [{s_label:22s}] Retained: {selection.selected_count:3d}/{meta.total_frames:3d} ({selection.retention_rate*100:4.1f}%) | "
                  f"File: {meta.file_size_mb:.2f}MB -> {out_size_mb:.2f}MB ({file_reduction_pct:4.1f}%) | "
                  f"Time: {selection.processing_time_sec:4.2f}s | Proxy: {proxy_result.proxy_fidelity_score:.2f}")

    # Save JSON results
    json_path = RESULTS_DIR / "validation_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved structured validation results to: {json_path}")

    # Save CSV summary
    csv_path = RESULTS_DIR / "validation_summary.csv"
    if csv_rows:
        with open(csv_path, "w", newline="") as f:
            writer_csv = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer_csv.writeheader()
            writer_csv.writerows(csv_rows)
        print(f"Saved tabular validation summary to: {csv_path}")

    return all_results

if __name__ == "__main__":
    run_validation()
