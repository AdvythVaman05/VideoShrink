import sys
import argparse
import json
import csv
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.video.reader import VideoReader
from backend.app.evaluation.cv_benchmark import (
    DownstreamCVBenchmarkRunner,
    SyntheticGroundTruth,
    DenseReferenceTracker,
    GroundTruthSequence,
)
from sample_data.generate_sample_video import generate_synthetic_video

RESULTS_DIR = BASE_DIR / "experiments" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def parse_args():
    parser = argparse.ArgumentParser(
        description="VideoShrink Downstream Computer Vision Benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--video",
        type=str,
        default=str(BASE_DIR / "sample_data" / "benchmark_sample.mp4"),
        help="Path to test video (e.g. sample_data/benchmark_sample.mp4 or experiments/test_videos/video_c_fast_action.mp4)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_DIR / "cv_benchmark_results.json"),
        help="Path to output JSON results"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=str(RESULTS_DIR / "cv_benchmark_summary.csv"),
        help="Path to output CSV summary"
    )
    return parser.parse_args()

def compute_pareto_frontier(results: List[Dict[str, Any]]) -> List[str]:
    """
    Identifies configurations on the Pareto-optimal frontier
    (maximizing frame_reduction_pct and track_retention_ratio).
    """
    pareto_labels = []
    for r1 in results:
        dominated = False
        r1_red = r1["frame_reduction_pct"]
        r1_ret = r1["track_retention_ratio"]
        for r2 in results:
            if r1 == r2:
                continue
            r2_red = r2["frame_reduction_pct"]
            r2_ret = r2["track_retention_ratio"]
            # r2 dominates r1 if r2 is >= in both and strictly > in at least one
            if (r2_red >= r1_red and r2_ret >= r1_ret) and (r2_red > r1_red or r2_ret > r1_ret):
                dominated = True
                break
        if not dominated:
            pareto_labels.append(r1["label"])
    return pareto_labels

def main():
    args = parse_args()
    video_path = Path(args.video)

    # Ensure sample video exists if requested
    if not video_path.exists():
        if "benchmark_sample" in video_path.name:
            print(f"Sample video {video_path} not found. Generating synthetic benchmark video...")
            generate_synthetic_video(output_path=video_path)
        else:
            print(f"Error: Video file not found at {video_path}")
            sys.exit(1)

    is_synthetic = "benchmark_sample" in video_path.name or "synthetic" in video_path.name
    gt_desc = (
        "Analytical Procedural Ground Truth (Exact mathematical coordinates)"
        if is_synthetic else
        "Algorithmic Dense Reference Trajectory (OpenCV MOG2 Tracking - NOT human ground truth)"
    )
    print("=" * 108)
    print("VIDEOSHRINK DOWNSTREAM COMPUTER-VISION BENCHMARK")
    print(f"Evaluating Video: {video_path.name}")
    print(f"Reference Type:  {gt_desc}")
    print("Downstream Task: Visual Object Tracking (mIoU, Centroid RMSE) & Scene Cut Proximity")
    print("=" * 108)

    reader = VideoReader(video_path)
    meta = reader.get_metadata()
    print(f"Resolution: {meta.width}x{meta.height} | Native FPS: {meta.fps} | Total Frames: {meta.total_frames} | Duration: {meta.duration_seconds:.1f}s")
    print("-" * 108)

    results = DownstreamCVBenchmarkRunner.run_benchmark(video_path=video_path)
    pareto_set = set(compute_pareto_frontier(results))

    # Print Table
    header = (
        f"{'Strategy / Configuration':<36} | {'Red %':>6} | {'FPS':>5} | "
        f"{'mIoU':>6} | {'RMSE(px)':>8} | {'Retention':>9} | {'Loss %':>6} | "
        f"{'CutRec':>6} | {'Latency':>7} | {'CAES':>6} | {'Pareto':>6}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        is_pareto = "YES" if r["label"] in pareto_set else " "
        cut_rec_str = f"{r['scene_cut_recall']*100:5.0f}%" if r["scene_cut_recall"] is not None else "   N/A"
        cut_lat_str = f"{r['scene_cut_latency_ms']:5.0f}ms" if r["scene_cut_latency_ms"] is not None else "    N/A"
        print(
            f"{r['label']:<36} | {r['frame_reduction_pct']:5.1f}% | {r['effective_fps']:5.1f} | "
            f"{r['mean_iou']:6.3f} | {r['centroid_rmse_px']:8.1f} | {r['track_retention_ratio']*100:8.1f}% | {r['track_loss_rate_pct']:5.1f}% | "
            f"{cut_rec_str:>6} | {cut_lat_str:>7} | {r['efficiency_score_caes']:6.3f} | {is_pareto:>6}"
        )

    print("-" * len(header))
    print("Table Notes:")
    print(" - CAES: Project-defined Compression-Accuracy Efficiency Score (harmonic mean of reduction rate & retention ratio).")
    print(" - CutRec/Latency: Nearest sampled keyframe proximity to annotated scene cut boundaries (N/A if no cuts annotated).")
    if is_synthetic:
        print(" - Note: Synthetic video transitions occur at integer-second marks (3.0s, 6.0s, 8.0s), which align with integer FPS divisors.")

    # Save JSON
    out_json = Path(args.output)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(
            {
                "video": video_path.name,
                "ground_truth_type": "analytical_synthetic" if is_synthetic else "dense_reference_trajectory",
                "metadata": meta.to_dict(),
                "pareto_optimal_strategies": list(pareto_set),
                "benchmark_results": results,
            },
            f,
            indent=2
        )
    print(f"\nSaved structured JSON results: {out_json}")

    # Save CSV
    out_csv = Path(args.csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_rows = []
    for r in results:
        csv_rows.append({
            "Video": video_path.name,
            "Strategy": r["strategy"],
            "Configuration": r["label"],
            "Original Frames": r["original_frames"],
            "Selected Frames": r["selected_frames"],
            "Frame Reduction %": f"{r['frame_reduction_pct']:.2f}%",
            "Effective FPS": f"{r['effective_fps']:.2f}",
            "Processing Time (s)": r["processing_time_sec"],
            "Mean IoU": r["mean_iou"],
            "Centroid RMSE (px)": r["centroid_rmse_px"],
            "Track Retention %": f"{r['track_retention_ratio']*100:.2f}%",
            "Track Loss Rate %": f"{r['track_loss_rate_pct']:.2f}%",
            "Scene Cut Recall %": f"{r['scene_cut_recall']*100:.1f}%" if r["scene_cut_recall"] is not None else "N/A",
            "Scene Cut Latency (ms)": f"{r['scene_cut_latency_ms']:.1f}" if r["scene_cut_latency_ms"] is not None else "N/A",
            "CAES Efficiency Score": r["efficiency_score_caes"],
            "Pareto Optimal": "YES" if r["label"] in pareto_set else "NO",
        })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved tabular CSV summary: {out_csv}")

    # Research Findings Summary
    print("\n" + "=" * 65)
    print("RESEARCH SUMMARY & KEY FINDINGS")
    print("=" * 65)
    dense = next((r for r in results if r["strategy"] == "dense_baseline"), None)
    uniform_sample = next((r for r in results if r["strategy"] == "uniform"), None)
    motion_bal = next((r for r in results if "Motion-Aware (Balanced)" in r["label"]), None)

    if dense:
        print(f"1. Dense Baseline ({dense['effective_fps']:.0f} FPS): mIoU = {dense['mean_iou']:.3f}, RMSE = {dense['centroid_rmse_px']:.1f}px (0% frame reduction)")
    if uniform_sample:
        print(f"2. {uniform_sample['label']}: mIoU = {uniform_sample['mean_iou']:.3f}, RMSE = {uniform_sample['centroid_rmse_px']:.1f}px ({uniform_sample['frame_reduction_pct']:.1f}% reduction)")
    if motion_bal:
        print(f"3. Motion-Aware (Balanced): mIoU = {motion_bal['mean_iou']:.3f}, RMSE = {motion_bal['centroid_rmse_px']:.1f}px ({motion_bal['frame_reduction_pct']:.1f}% reduction)")
    print(f"4. Pareto Optimal Operating Points: {', '.join(pareto_set)}")
    print("=" * 65)

if __name__ == "__main__":
    main()
