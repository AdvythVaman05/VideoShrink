import os
import sys
import json
import time
from pathlib import Path
import streamlit as st
import pandas as pd

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.config import settings
from backend.app.video.reader import VideoReader
from backend.app.video.writer import VideoWriter
from backend.app.sampling.selector import FrameSelector
from backend.app.analysis.failure import FailureAnalyzer
from backend.app.evaluation.metrics import ReductionMetrics
from backend.app.evaluation.benchmark import VisualPreservationProxyEvaluator
from backend.app.evaluation.comparison import StrategyComparator
from backend.app.db.database import db
from frontend.components.charts import create_motion_timeline_chart
from frontend.components.timeline import render_timeline_barcode_html
from frontend.components.frame_inspector import render_frame_inspector

st.set_page_config(
    page_title="VideoShrink | Dataset Frame Pruning",
    page_icon="🎞️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-title { font-size: 13px; color: #8b949e; margin-bottom: 4px; font-weight: 500; }
    .metric-value { font-size: 26px; font-weight: 700; color: #58a6ff; }
    .metric-subtitle { font-size: 11px; color: #7ee787; margin-top: 4px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 18px;
        background-color: #161b22;
        border-radius: 6px;
        border: 1px solid #30363d;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f6feb !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.title("🎞️ VideoShrink")
st.markdown("#### **Information-Preserving Video Dataset Compression for Computer Vision**")
st.caption(
    "Intelligently prune redundant visual frames while preserving critical scene changes, motion dynamics, "
    "and information fidelity for downstream ML training and evaluation."
)

st.markdown("""
> **Key Principle**: VideoShrink optimizes for **visual information preservation vs. frame reduction**, *not* conventional lossy codec compression. 
> Removing redundant frames reduces downstream vision pipeline latency, storage, and training FLOPs while preserving temporal semantics.
""")

# Sidebar Controls
st.sidebar.header("1. Input Video Source")

sample_video_path = BASE_DIR / "sample_data" / "benchmark_sample.mp4"
use_sample = st.sidebar.button("🎬 Load Synthetic Benchmark Video", use_container_width=True)

uploaded_file = st.sidebar.file_uploader(
    "Or upload custom video (MP4, MOV, AVI, MKV)",
    type=["mp4", "mov", "avi", "mkv"],
    help="Upload a video up to 250MB."
)

# Manage active video path in session state
if "active_video_path" not in st.session_state:
    st.session_state["active_video_path"] = None
if "active_video_name" not in st.session_state:
    st.session_state["active_video_name"] = None

if use_sample and sample_video_path.exists():
    st.session_state["active_video_path"] = sample_video_path
    st.session_state["active_video_name"] = "benchmark_sample.mp4"
    st.sidebar.success("Loaded synthetic benchmark video!")
elif uploaded_file is not None:
    save_path = settings.UPLOAD_DIR / f"upload_{uploaded_file.name}"
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.session_state["active_video_path"] = save_path
    st.session_state["active_video_name"] = uploaded_file.name

video_path = st.session_state.get("active_video_path")
video_name = st.session_state.get("active_video_name")
meta = None

if video_path is not None and Path(video_path).exists():
    try:
        reader = VideoReader(video_path)
        meta = reader.get_metadata()
    except Exception as e:
        st.error(f"Failed to read video: {e}")

# Video Metadata Bar
if meta is not None:
    with st.expander("📊 Input Video Metadata & Diagnostics", expanded=True):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Filename", meta.filename[:16] + ("..." if len(meta.filename) > 16 else ""))
        col2.metric("Resolution", f"{meta.width} × {meta.height}")
        col3.metric("Native FPS", f"{meta.fps:.2f}")
        col4.metric("Total Frames", f"{meta.total_frames:,}")
        col5.metric("Duration", f"{meta.duration_seconds:.2f}s")
        col6.metric("File Size", f"{meta.file_size_mb:.2f} MB")
else:
    st.info("👋 Select a video to begin: Click **'Load Synthetic Benchmark Video'** in the sidebar or upload an MP4/MOV file.")

# Main Navigation Tabs
tab_single, tab_compare, tab_history = st.tabs([
    "🔬 Single Strategy Optimization",
    "⚖️ Multi-Strategy Comparison Benchmark",
    "📜 Experiment History (SQLite)"
])

# -------------------------------------------------------------
# TAB 1: Single Strategy Optimization
# -------------------------------------------------------------
with tab_single:
    if meta is None:
        st.warning("⚠️ Please load or upload a video using the sidebar first.")
    else:
        st.subheader("Configure Sampling Strategy")
        st.sidebar.header("2. Strategy & Parameters")

        strategy = st.sidebar.selectbox(
            "Sampling Strategy",
            options=["Motion-Aware (Adaptive)", "Perceptual Similarity", "Uniform Sampling (Baseline)"],
            index=0,
            help="Select between intelligent motion-aware, perceptual difference, or uniform baseline."
        )

        strategy_code = "motion_aware"
        strategy_params = {}

        if strategy == "Uniform Sampling (Baseline)":
            strategy_code = "uniform"
            st.sidebar.caption("Keeps every k-th frame. Fast baseline for frame-reduction comparison.")
            target_fps = st.sidebar.slider("Target FPS", min_value=1.0, max_value=float(meta.fps), value=min(10.0, float(meta.fps)), step=1.0)
            strategy_params = {"target_fps": target_fps}

        elif strategy == "Perceptual Similarity":
            strategy_code = "perceptual"
            st.sidebar.caption("Removes frames that are visually redundant against the previous kept frame.")
            sim_threshold = st.sidebar.slider(
                "Similarity Threshold",
                min_value=0.80, max_value=0.99, value=0.96, step=0.01,
                help="Higher value retains more subtle visual changes. Lower value drops more frames."
            )
            max_gap = st.sidebar.slider(
                "Maximum Periodic Anchor (seconds)",
                min_value=1.0, max_value=6.0, value=2.5, step=0.5,
                help="Guarantees at least one frame every N seconds to avoid temporal blindspots."
            )
            strategy_params = {"similarity_threshold": sim_threshold, "max_interval_sec": max_gap}

        else:
            strategy_code = "motion_aware"
            st.sidebar.caption("Dynamically adjusts frame density using Farneback optical flow and scene-cut detection.")
            motion_sens = st.sidebar.slider("Motion Sensitivity", min_value=0.1, max_value=1.0, value=0.5, step=0.05)
            col_fps1, col_fps2 = st.sidebar.columns(2)
            min_fps = col_fps1.number_input("Min FPS (Floor)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
            max_fps = col_fps2.number_input("Max FPS (Ceiling)", min_value=5.0, max_value=float(meta.fps), value=min(15.0, float(meta.fps)), step=1.0)
            scene_cut = st.sidebar.slider("Scene Cut Sensitivity", min_value=0.20, max_value=0.60, value=0.35, step=0.05)
            strategy_params = {
                "motion_sensitivity": motion_sens,
                "min_fps": min_fps,
                "max_fps": max_fps,
                "scene_cut_threshold": scene_cut
            }

        generate_video_opt = st.sidebar.checkbox("Generate playable optimized MP4", value=True)

        # Process Button
        if st.button("🚀 Run Frame Pruning & Optimization", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Initializing sampling pipeline...")
            status_text = st.empty()

            start_time = time.time()

            # Step 1: Run frame selection
            status_text.text("Extracting and sampling frames...")
            progress_bar.progress(20, text="Analyzing video frames...")

            def progress_hook(pct, msg):
                progress_bar.progress(int(10 + pct * 0.5), text=msg)

            selection = FrameSelector.run_selection(
                strategy_name=strategy_code,
                reader=reader,
                params=strategy_params,
                progress_callback=progress_hook
            )

            # Step 2: Quality & Failure Analysis
            status_text.text("Evaluating failure risks and sensitive segments...")
            progress_bar.progress(65, text="Running failure risk detection...")
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

            # Step 3: Visual Preservation Proxy Evaluation
            status_text.text("Computing visual data preservation proxy score...")
            progress_bar.progress(75, text="Evaluating visual proxy heuristics...")
            evaluator = VisualPreservationProxyEvaluator()
            proxy_result = evaluator.evaluate(reader, selection)

            # Step 4: Output Video Generation
            output_video_path = None
            compressed_size_bytes = None
            file_reduction_pct = None

            if generate_video_opt and selection.selected_indices:
                status_text.text("Synthesizing optimized MP4 via FFmpeg...")
                progress_bar.progress(85, text="Encoding optimized video...")
                writer = VideoWriter()
                out_file = settings.PROCESSED_DIR / f"opt_{Path(video_path).stem}_{strategy_code}.mp4"
                written = writer.write_selected_frames(
                    source_video_path=video_path,
                    selected_indices=selection.selected_indices,
                    output_video_path=out_file,
                    preserve_duration=True
                )
                if written.exists():
                    output_video_path = written
                    compressed_size_bytes = written.stat().st_size
                    if meta.file_size_bytes > 0:
                        saved = meta.file_size_bytes - compressed_size_bytes
                        file_reduction_pct = round((saved / meta.file_size_bytes) * 100.0, 2)

            # Step 5: Save experiment to SQLite
            clean_name = meta.filename.split("_", 1)[-1] if "_" in meta.filename else meta.filename

            import numpy as np
            kept_records = [r for r in selection.frame_records if r.is_selected]
            if kept_records:
                mean_blur = float(np.mean([r.blur_score for r in kept_records if r.blur_score is not None] or [0.0]))
                mean_bright = float(np.mean([r.brightness for r in kept_records if r.brightness is not None] or [0.0]))
                mean_contrast = float(np.mean([r.contrast for r in kept_records if r.contrast is not None] or [0.0]))
                blurry_count = sum(1 for r in kept_records if r.is_blurry)
            else:
                mean_blur, mean_bright, mean_contrast, blurry_count = 0.0, 0.0, 0.0, 0

            quality_summary = {
                "mean_blur_score": round(mean_blur, 2),
                "mean_brightness": round(mean_bright, 2),
                "mean_contrast": round(mean_contrast, 2),
                "blurry_frames_count": blurry_count
            }

            exp_id = db.create_experiment(
                video_filename=clean_name,
                video_duration=meta.duration_seconds,
                strategy=strategy_code,
                parameters=strategy_params,
                original_frames=meta.total_frames,
                selected_frames=selection.selected_count,
                retention_rate=selection.retention_rate,
                reduction_rate=selection.reduction_rate,
                effective_fps=selection.effective_fps,
                original_size_bytes=meta.file_size_bytes,
                compressed_size_bytes=compressed_size_bytes,
                file_size_reduction_pct=file_reduction_pct,
                processing_time_sec=selection.processing_time_sec,
                info_preservation_score=proxy_result.proxy_fidelity_score,
                output_video_path=str(output_video_path) if output_video_path else None,
                failure_summary={
                    "sensitive_segments_count": len(sensitive_segments),
                    "segments": [s.__dict__ for s in sensitive_segments]
                },
                quality_summary=quality_summary
            )

            progress_bar.progress(100, text="Processing complete!")
            status_text.empty()

            # Cache results in session state
            st.session_state["latest_results"] = {
                "exp_id": exp_id,
                "strategy": strategy,
                "strategy_code": strategy_code,
                "selection": selection,
                "proxy_result": proxy_result,
                "sensitive_segments": sensitive_segments,
                "output_video_path": output_video_path,
                "compressed_size_bytes": compressed_size_bytes,
                "file_reduction_pct": file_reduction_pct,
            }

        # Render Results if available
        if "latest_results" in st.session_state:
            res = st.session_state["latest_results"]
            sel = res["selection"]
            proxy_res = res["proxy_result"]

            st.markdown("---")
            st.subheader("🎯 Optimization Results & Scorecards")

            # Metric Cards
            mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
            with mcol1:
                st.metric(
                    "Frames Pruned",
                    f"{sel.reduction_rate * 100.0:.1f}%",
                    delta=f"-{sel.total_frames - sel.selected_count} frames",
                    delta_color="normal"
                )
            with mcol2:
                st.metric(
                    "Frames Retained",
                    f"{sel.retention_rate * 100.0:.1f}%",
                    delta=f"{sel.selected_count} / {sel.total_frames}"
                )
            with mcol3:
                st.metric(
                    "Effective FPS",
                    f"{sel.effective_fps:.1f} FPS",
                    delta=f"from {meta.fps:.1f} FPS"
                )
            with mcol4:
                file_red = res.get("file_reduction_pct")
                st.metric(
                    "File Size Reduction",
                    f"{file_red:.1f}%" if file_red is not None else "N/A",
                    delta=f"{round((res.get('compressed_size_bytes') or 0)/(1024*1024), 2)} MB" if res.get('compressed_size_bytes') else None
                )
            with mcol5:
                st.metric(
                    "Visual Preservation (Proxy)",
                    f"{proxy_res.proxy_fidelity_score * 100.0:.1f}%",
                    delta="Analytical Proxy"
                )

            st.caption(
                "⚠️ **Visual/Data Preservation Metric (Proxy Heuristic)**: "
                "This score measures peak motion coverage, temporal continuity, and sharpness. "
                "*It is NOT equivalent to downstream ML performance.* Downstream task retention (e.g. classification Top-1, detection mAP) "
                "requires evaluating an actual model on the dataset."
            )

            # Video Comparison Display
            st.markdown("### 🎬 Visual Playback Comparison")
            vcol1, vcol2 = st.columns(2)
            with vcol1:
                st.markdown(f"**Original Video ({meta.fps:.1f} FPS, {meta.total_frames} frames)**")
                st.video(str(video_path))
            with vcol2:
                if res.get("output_video_path") and Path(res["output_video_path"]).exists():
                    st.markdown(f"**Optimized Video ({sel.effective_fps:.1f} FPS, {sel.selected_count} frames)**")
                    st.video(str(res["output_video_path"]))
                    
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        with open(res["output_video_path"], "rb") as f:
                            st.download_button(
                                label="⬇️ Download Optimized MP4",
                                data=f,
                                file_name=Path(res["output_video_path"]).name,
                                mime="video/mp4",
                                use_container_width=True
                            )
                    with btn_col2:
                        exp_json_str = db.export_experiment_json(res["exp_id"])
                        if exp_json_str:
                            st.download_button(
                                label="📄 Export Metadata (JSON)",
                                data=exp_json_str,
                                file_name=f"experiment_{res['exp_id'][:8]}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                else:
                    st.info("Video playback generation was disabled or unavailable.")

            # Visual Timeline Barcode
            st.markdown("### 📊 Visual Timeline & Density Barcode")
            st.caption("Visual representation comparing full temporal sampling against the sparse selection map.")
            timeline_dict_list = [r.to_dict() for r in sel.frame_records]
            barcode_html = render_timeline_barcode_html(timeline_dict_list, num_bins=80)
            st.components.v1.html(barcode_html, height=130)

            # Interactive Motion Profile Chart
            st.markdown("### 📈 Motion Energy & Frame Selection Profile")
            chart = create_motion_timeline_chart(timeline_dict_list)
            st.altair_chart(chart, use_container_width=True)

            # Failure Analysis Section
            st.markdown("### ⚠️ Failure Analysis: Potentially Sensitive Segments")
            st.caption(
                "Identifies high-motion bursts, scene transitions, or optical anomalies where aggressive pruning "
                "may cause information loss."
            )
            segments = res.get("sensitive_segments", [])
            if segments:
                for s in segments:
                    sev_icon = "🔴" if s.severity == "high" else "🟡"
                    with st.container():
                        st.markdown(
                            f"**{sev_icon} Time Interval: `{s.start_time_formatted}` – `{s.end_time_formatted}`** "
                            f"({s.end_sec - s.start_sec:.1f}s) | *{', '.join(s.reasons)}*"
                        )
                        st.caption(f"💡 *Recommendation: {s.recommendation}*")
            else:
                st.success("✅ No critical failure risks or sensitive high-entropy segments detected.")

            # Explainable Keyframe Inspector
            from backend.app.services.job_runner import job_runner
            previews = job_runner._extract_frame_previews(reader, sel, max_previews=12)
            render_frame_inspector(previews)

# -------------------------------------------------------------
# TAB 2: Multi-Strategy Comparison Benchmark
# -------------------------------------------------------------
with tab_compare:
    if meta is None:
        st.warning("⚠️ Please load or upload a video using the sidebar first.")
    else:
        st.subheader("⚖️ Comparative Strategy Benchmark")
        st.markdown("""
        Evaluate how **Uniform**, **Perceptual**, and **Motion-Aware** sampling compare on the exact same video.
        The goal is to determine which strategy achieves the highest visual information preservation at a target reduction rate.
        """)

        if st.button("🏁 Run Comparative Benchmark", type="secondary"):
            with st.spinner("Executing all 3 sampling strategies on the dataset..."):
                comparison_results = StrategyComparator.compare_strategies(reader)
                st.session_state["comparison_data"] = comparison_results

        if "comparison_data" in st.session_state:
            comp_df = pd.DataFrame(st.session_state["comparison_data"])
            
            # Display summary table
            display_df = comp_df[[
                "strategy", "selected_frames", "retention_pct", "reduction_pct",
                "effective_fps", "processing_time_sec", "visual_preservation_proxy_score"
            ]].rename(columns={
                "strategy": "Sampling Strategy",
                "selected_frames": "Frames Retained",
                "retention_pct": "Retention (%)",
                "reduction_pct": "Reduction (%)",
                "effective_fps": "Effective FPS",
                "processing_time_sec": "Compute Time (s)",
                "visual_preservation_proxy_score": "Visual Proxy Score (0-1)"
            })

            st.dataframe(display_df, use_container_width=True)
            st.caption(
                "⚠️ **Disclaimer**: The Visual Proxy Score is a temporal and optical coverage heuristic. "
                "It is NOT equivalent to downstream ML model performance."
            )

            # Bar chart comparison of retention vs fidelity
            chart_data = comp_df[["strategy", "retention_pct", "visual_preservation_proxy_score"]].copy()
            chart_data["Proxy Fidelity %"] = chart_data["visual_preservation_proxy_score"] * 100.0
            
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown("#### Frame Retention Rate (%)")
                st.bar_chart(chart_data.set_index("strategy")["retention_pct"])
            with col_c2:
                st.markdown("#### Visual Proxy Preservation (%)")
                st.bar_chart(chart_data.set_index("strategy")["Proxy Fidelity %"])

# -------------------------------------------------------------
# TAB 3: Experiment History
# -------------------------------------------------------------
with tab_history:
    st.subheader("📜 Experiment Logging & Reproducibility (SQLite)")
    st.caption("Every optimization run is tracked with hyperparameters, reduction metrics, and timestamps.")

    exp_records = db.list_experiments(limit=50)
    if exp_records:
        df_exp = pd.DataFrame(exp_records)
        cols_to_show = [
            "experiment_code", "created_at", "video_filename", "strategy",
            "original_frames", "selected_frames", "retention_rate", "effective_fps",
            "file_size_reduction_pct", "processing_time_sec"
        ]
        available_cols = [c for c in cols_to_show if c in df_exp.columns]
        st.dataframe(df_exp[available_cols], use_container_width=True)

        st.markdown("#### Export Reproducible Experiment Record")
        exp_codes = [e["experiment_code"] for e in exp_records]
        selected_code = st.selectbox("Select Experiment to export:", exp_codes)
        if selected_code:
            matching = [e for e in exp_records if e["experiment_code"] == selected_code]
            if matching:
                exp_entry = matching[0]
                json_str = db.export_experiment_json(exp_entry["id"])
                if json_str:
                    st.download_button(
                        label=f"⬇️ Download {selected_code} Metadata (JSON)",
                        data=json_str,
                        file_name=f"{selected_code}.json",
                        mime="application/json"
                    )
                    with st.expander("Inspect Raw Reproducibility JSON Payload"):
                        st.json(json.loads(json_str))
    else:
        st.info("No experiments recorded yet. Run an optimization to generate experiment records.")
