# VideoShrink: Information-Preserving Video Dataset Compression

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg?style=flat&logo=streamlit)](https://streamlit.io)
[![OpenCV](https://img.shields.io/badge/Computer_Vision-OpenCV-5C3EE8.svg?style=flat&logo=opencv)](https://opencv.org)
[![FFmpeg](https://img.shields.io/badge/Encoding-FFmpeg_H.264-007808.svg?style=flat&logo=ffmpeg)](https://ffmpeg.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Core Philosophy**: VideoShrink is a **visual dataset optimization and benchmarking system**. It intelligently reduces redundant visual frames from video datasets while preserving critical dynamics, scene transitions, and visual information required for computer-vision/ML tasks.

---

## 1. Frame Reduction vs. Codec Compression

In conventional media workflows, **video compression** refers to lossy or lossless transform-based encoding (H.264, HEVC, AV1) where DCT coefficients, macroblocks, and motion vectors minimize bitrate ($MB/sec$).

In contrast, **VideoShrink evaluates Information-Preserving Frame Reduction**:
* **Downstream Computer Vision Cost**: Neural networks (Video Transformers, 3D-CNNs, Object Trackers) decode and backpropagate on discrete uncompressed pixel tensors. A 30 FPS video that contains 80% static backgrounds consumes $5\times$ more training FLOPs, I/O memory bandwidth, and storage than necessary.
* **Intelligent Temporal Pruning**: VideoShrink strips visually redundant frames while keeping key dynamic transitions and high-motion events.
* **File-Size vs. Frame Reduction**: Removing frames naturally decreases video file size, but VideoShrink strictly distinguishes measured **frame reduction percentage** from **actual file-size reduction percentage**.

---

## 2. Problem & Motivation

Modern computer vision datasets (e.g., Kinetics-400, UCF101, Epic-Kitchens, self-driving telemetry, surveillance feeds) suffer from massive temporal redundancy:
1. **Stationary Cameras / Static Scenarios**: Extended intervals exhibit near-zero visual entropy.
2. **Compute Bottlenecks**: Processing redundant frames strains distributed data loaders and GPU tensor cores.
3. **Imbalanced Motion Information**: Uniform decimation (e.g., blindly dropping from 30 FPS to 6 FPS) indiscriminately discards critical micro-actions and fast transitions while retaining excess static frames.

**VideoShrink answers**: *Can we adaptively prune redundant video frames while preserving the visual information that matters for downstream ML pipelines?*

---

## 3. System Architecture

VideoShrink is decoupled so that frame-selection algorithms are completely independent of video reconstruction or dataset export formats.

```
VideoShrink/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI server & route orchestration
│   │   ├── config.py                # Environment and limits configuration
│   │   ├── api/                     # REST API (/upload, /process, /status, /results, /download, /experiments)
│   │   ├── video/
│   │   │   ├── reader.py            # Streaming VideoReader (sequential generator, O(1) RAM)
│   │   │   ├── writer.py            # VideoWriter (FFmpeg H.264/yuv420p & OpenCV fallback)
│   │   │   └── metadata.py          # VideoMetadata dataclass
│   │   ├── sampling/
│   │   │   ├── base.py              # BaseSampler interface & FrameRecord schema
│   │   │   ├── uniform.py           # Strategy A: Uniform FPS baseline
│   │   │   ├── perceptual.py        # Strategy B: Grayscale perceptual similarity
│   │   │   ├── motion_aware.py      # Strategy C: Optical flow & scene-adaptive retention
│   │   │   └── selector.py          # Strategy factory & orchestrator
│   │   ├── analysis/
│   │   │   ├── similarity.py        # Normalized L1 difference & histogram correlation
│   │   │   ├── motion.py            # Farneback optical flow & scene cut detection
│   │   │   ├── quality.py           # Laplacian blur variance, contrast, exposure
│   │   │   └── failure.py           # Sensitive segment detection & failure diagnostics
│   │   ├── evaluation/
│   │   │   ├── metrics.py           # ReductionMetrics (frames %, file %, effective FPS)
│   │   │   ├── benchmark.py         # Visual proxy heuristic & Phase 2 ML stub
│   │   │   └── comparison.py        # Multi-strategy comparative benchmark runner
│   │   ├── storage/                 # Local filesystem storage abstraction (S3 ready)
│   │   ├── db/                      # SQLite experiment logging & JSON reproducibility
│   │   └── services/                # In-memory background job runner with live progress
│   └── tests/                       # Complete Pytest test suite
├── frontend/
│   ├── streamlit_app.py             # Streamlit technical UI & diagnostics dashboard
│   └── components/                  # Barcode timeline, Altair motion graphs, frame preview
├── sample_data/                     # Synthetic benchmark video generator
├── Dockerfile                       # Railway-ready production container
└── docker-compose.yml               # Multi-service local orchestration
```

### Memory Footprint Guarantee
Full videos are **never buffered into RAM**.
* `VideoReader.iter_frames()` yields sequential downsampled frames ($160 \times 90$) for metric calculation and immediately releases pixel buffers.
* Output video reconstruction pipes selected frames sequentially to `ffmpeg` via standard input.

---

## 4. Sampling Strategies

### Strategy A: Uniform Sampling (Deterministic Baseline)
* Drops frames at fixed strides: $\text{stride} = \lfloor \frac{\text{FPS}_{\text{orig}}}{\text{FPS}_{\text{target}}} \rfloor$.
* Serves as the naive baseline against which intelligent adaptive algorithms are benchmarked.

### Strategy B: Perceptual Similarity Sampling
* Measures normalized visual difference $\Delta(F_t, F_{\text{ref}})$ against the last retained frame:
  $$\text{Similarity}(F_t, F_{\text{ref}}) = 1.0 - \frac{1}{255 \cdot W \cdot H} \sum_{x,y} |F_t(x,y) - F_{\text{ref}}(x,y)|$$
* If $\text{Similarity} < \theta_{\text{sim}}$ (default `0.96`), the frame represents meaningful visual change and is retained as the new reference frame.
* Incorporates a maximum periodic anchor (e.g. 2.5s) to prevent unbounded temporal dropouts during long static scenes.

### Strategy C: Motion-Aware & Scene-Aware Adaptive Sampling
* Calculates dense optical flow magnitude using Farneback flow on downsampled frames:
  $$\mathbf{u}, \mathbf{v} = \text{OpticalFlow}(F_{t-1}, F_t), \quad \text{Motion} = \min\left(1.0, \frac{\overline{\sqrt{\mathbf{u}^2 + \mathbf{v}^2}}}{5.0}\right)$$
* **Scene Cut Detection**: If frame difference $> 0.20$ or flow surges sharply, an abrupt scene cut is detected, instantly forcing frame retention and resetting the reference.
* **Adaptive Sampling Density**: Dynamically scales instantaneous target FPS between $\text{FPS}_{\min}$ (floor) and $\text{FPS}_{\max}$ (ceiling):
  $$\text{FPS}_{\text{target}}(t) = \text{FPS}_{\min} + (\text{FPS}_{\max} - \text{FPS}_{\min}) \cdot (\text{Motion} \cdot (1 + \gamma))^\alpha$$
* **Explainable Output**: Every frame receives an explicit selection rationale (e.g., `"High motion burst"`, `"Scene transition detected"`, `"Static interval anchor"`).

---

## 5. Benchmarking Methodology: Proxy Metrics vs. Downstream ML

> ⚠️ **IMPORTANT CLARIFICATION ON PROXY METRICS**:
> VideoShrink does **not** present the Information Preservation Score as equivalent to downstream ML performance.
> It is an **analytical proxy heuristic** measuring:
> 1. **Peak Motion Coverage**: Proportion of original high-motion peaks captured by selected frames.
> 2. **Temporal Continuity**: Absence of severe temporal dropouts ($> 4\text{s}$).
> 3. **Sharpness Ratio**: Ratio of retained frames that are sharp vs blurry (Laplacian variance $> 100$).
>
> **Never claim that a compression strategy 'preserves model performance' without evaluating an actual downstream neural network on both the original and compressed datasets.**

### Phase 2 PyTorch Downstream Benchmark Extension
The system provides a clean extension interface in `backend/app/evaluation/benchmark.py`:
```python
class DownstreamMLBenchmark(ABC):
    @abstractmethod
    def evaluate_downstream_task(
        self, original_video_path: str, optimized_video_path: str, task_type: str
    ) -> Dict[str, Any]:
        """
        Phase 2 implementation:
        1. Pass original and compressed video clips through PyTorch model (e.g. VideoMAE / R3D-18 / YOLOv8).
        2. Measure Task Accuracy Delta (Top-1 Acc, Top-5 Acc, mAP).
        3. Quantify downstream training FLOPs saved and data loading throughput speedup.
        """
        pass
```

---

## 6. Failure Analysis Framework

Pruning frames from video datasets introduces potential failure modes where critical information can be lost. VideoShrink automatically flags **sensitive temporal segments**:
* **High-Motion Bursts**: Rapid camera panning or fast foreground motion.
* **Scene Transitions**: Cuts where aggressive pruning could lose scene context.
* **Optical Anomalies**: Extreme underexposure ($< 25$), overexposure ($> 230$), or motion blur.

Each segment provides timecodes (e.g. `00:06 – 00:08`), severity (`high`/`medium`), and actionable recommendations.

---

## 7. Experiment Reproducibility & JSON Export

Every run is logged into SQLite (`experiments/videoshrink.db`) and is fully reproducible. The system exports structured JSON containing:
* Input video metadata (dimensions, native FPS, total frames, file size)
* Sampling strategy & exact hyperparameters
* Frame counts (original, selected, removed, retention ratio)
* Processing latency and throughput (FPS/sec)
* Actual output file size and compression percentage
* Quality summary metrics (mean blur, brightness, contrast)
* Sensitive segment failure diagnostics
* Visual preservation proxy score and explicit disclaimer

---

## 8. Installation & Running Locally

### Prerequisites
* Python 3.10+ (tested on Python 3.11 - 3.14)
* FFmpeg (installed and available on system `PATH`)

### Quick Setup

```bash
## 8. Real-World Validation

To evaluate algorithmic behavior under diverse computer-vision data conditions, VideoShrink was evaluated across a validation suite of 5 real-world videos representing distinct operational domains:

1. **Category A (Talking Head / Interview)**: `video_a_talking_head.mp4` (768×432, 12 FPS, 8.0s) — Single speaker with subtle head gestures, eye movements, and static indoor background.
2. **Category B (Lecture / Presentation)**: `video_b_lecture_presentation.mp4` (1920×1080 Full HD, 30 FPS, 8.0s) — Stationary classroom camera, seated students, occasional hand/head motion.
3. **Category C (Fast Action / Dynamic Motion)**: `video_c_fast_action.mp4` (768×432, 12 FPS, 8.0s) — Traffic scene with vehicles, bicycles, and pedestrians crossing against a wide background.
4. **Category D (Outdoor Movement / Walking)**: `video_d_outdoor_movement.mp4` (768×432, 12 FPS, 8.0s) — Pedestrian tracking with shifting shadows and outdoor illumination.
5. **Category E (Multi-Scene Transitions)**: `video_e_multi_scene_cuts.mp4` (640×360, 17.8 FPS, 9.0s) — Sequence containing 2 abrupt real-world scene cuts between distinct indoor and outdoor scenes.

### Validation Methodology & Parameters
* **Uniform Baseline**: Target FPS = $10.0$ (with fractional phase accumulation).
* **Perceptual Similarity**: Similarity Threshold = $0.96$, Max Periodic Anchor = $2.5\text{s}$.
* **Motion-Aware Adaptive**: Motion Sensitivity = $0.5$, $\text{FPS}_{\min} = 2.0$, $\text{FPS}_{\max} = 15.0$, Scene Cut Threshold = $0.35$.
* Every run reconstructed a playable MP4 with FFmpeg ($H.264/\text{yuv420p}$) and logged full JSON metrics.

### Measured Validation Results

| Video Category | Strategy | Orig Frames | Selected Frames | Frame Red. % | Retention % | Effective FPS | Orig Size | Opt Size | File Red. % | Proc Time | Throughput | Sensitive Segments | Visual Proxy Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A. Talking Head** | Uniform | 96 | 81 | 15.6% | 84.4% | 10.1 | 0.35 MB | 0.36 MB | -2.6% | 0.14s | 678 FPS | 1 | 0.98 |
| | Perceptual | 96 | 13 | 86.5% | 13.5% | 1.6 | 0.35 MB | 0.16 MB | 55.1% | 0.16s | 616 FPS | 1 | 0.64 |
| | Motion-Aware | 96 | 21 | **78.1%** | **21.9%** | **2.6** | 0.35 MB | 0.20 MB | **42.2%** | 0.34s | 283 FPS | 1 | **0.97** |
| **B. Lecture (1080p)**| Uniform | 240 | 82 | 65.8% | 34.2% | 10.2 | 2.56 MB | 1.79 MB | 30.3% | 1.26s | 190 FPS | 0 | 1.00 |
| | Perceptual | 240 | 6 | 97.5% | 2.5% | 0.8 | 2.56 MB | 0.60 MB | 76.5% | 1.33s | 181 FPS | 0 | 0.60 |
| | Motion-Aware | 240 | 20 | **91.7%** | **8.3%** | **2.5** | 2.56 MB | 1.10 MB | **57.2%** | 1.80s | 133 FPS | 0 | **0.73** |
| **C. Fast Action** | Uniform | 96 | 81 | 15.6% | 84.4% | 10.1 | 0.35 MB | 0.30 MB | 13.9% | 0.17s | 564 FPS | 0 | 1.00 |
| | Perceptual | 96 | 5 | 94.8% | 5.2% | 0.6 | 0.35 MB | 0.10 MB | 71.8% | 0.17s | 569 FPS | 0 | 0.65 |
| | Motion-Aware | 96 | 20 | **79.2%** | **20.8%** | **2.5** | 0.35 MB | 0.21 MB | **39.8%** | 0.34s | 278 FPS | 0 | **1.00** |
| **D. Outdoor Walking**| Uniform | 96 | 81 | 15.6% | 84.4% | 10.1 | 0.34 MB | 0.33 MB | 1.1% | 0.14s | 708 FPS | 0 | 1.00 |
| | Perceptual | 96 | 6 | 93.8% | 6.2% | 0.8 | 0.34 MB | 0.10 MB | 70.6% | 0.15s | 632 FPS | 0 | 0.67 |
| | Motion-Aware | 96 | 23 | **76.0%** | **24.0%** | **2.9** | 0.34 MB | 0.20 MB | **39.6%** | 0.35s | 278 FPS | 0 | **1.00** |
| **E. Multi-Scene Cuts**| Uniform | 162 | 92 | 43.2% | 56.8% | 10.1 | 0.24 MB | 0.22 MB | 7.1% | 0.09s | 1749 FPS | 1 | 1.00 |
| | Perceptual | 162 | 7 | 95.7% | 4.3% | 0.8 | 0.24 MB | 0.10 MB | 56.0% | 0.13s | 1241 FPS | 1 | 0.60 |
| | Motion-Aware | 162 | 23 | **85.8%** | **14.2%** | **2.5** | 0.24 MB | 0.16 MB | **31.4%** | 0.44s | 371 FPS | 2 | **0.93** |

*Raw experimental data: `experiments/results/validation_summary.csv` and `experiments/results/validation_results.json`.*

---

### Empirical Findings & Failure Analysis

1. **Frame Reduction vs. File-Size Decoupling**:
   - On `video_a_talking_head.mp4`, Uniform Sampling with decimation from 12 FPS to 10.1 FPS reduced frames by 15.6%, but the resulting MP4 file was **2.6% larger** (0.35MB $\rightarrow$ 0.36MB). This conclusively proves that **frame reduction does not guarantee file size reduction**, due to fixed container overhead and keyframe quantization.
2. **Perceptual Similarity Failure Mode (Localized Motion on Static Background)**:
   - On `video_c_fast_action.mp4`, vehicles and cyclists moved across the street but occupied only 3–5% of the total frame pixels.
   - The global mean difference between consecutive frames was only $0.0017$ (less than $0.2\%$).
   - As a result, Perceptual Similarity classified the entire scene as "visually redundant", retaining only 5 periodic anchor frames and missing intermediate vehicles.
   - **Resolution**: Integrated a $4 \times 4$ spatial grid block-pooling step into `compute_frame_difference` ($0.70 \times \text{mean} + 0.30 \times \max_{\text{block}}$) so localized activity contributes to the distance metric.
3. **Motion-Aware Optical Flow Success**:
   - Because Farneback dense optical flow measures velocity vectors rather than area-weighted pixel intensity differences, it reliably detected the moving vehicles in `video_c` and retained 20 representative frames with a **1.00 Visual Proxy Score**.
   - On `video_b` (1080p Lecture), Motion-Aware achieved a **91.7% frame reduction** (dropping 220 redundant static frames), reducing file size by 57.2% with zero pipeline crashes.
4. **Scene Cut Boundary Preservation**:
   - On `video_e_multi_scene_cuts.mp4`, Motion-Aware detected the cuts at $t=3.0\text{s}$ and $t=6.0\text{s}$, retaining the boundary frames and logging 2 sensitive segment warnings for operator review.

---

### Algorithm Refinements Implemented During Validation

1. **Fractional FPS Phase Accumulator** (`backend/app/sampling/uniform.py`):
   - Replaced integer stride rounding (`stride = round(orig_fps / target_fps)`) with a continuous phase accumulator `int(idx * (target_fps / orig_fps))`.
   - Prevents integer decimation collapse on videos with native rates near the target (e.g. 12 FPS $\rightarrow$ 10 FPS was previously rounded to stride 1 with 0% reduction; now accurately achieves 10.1 FPS).
2. **Spatial Block-Pooled Difference** (`backend/app/analysis/similarity.py`):
   - Added $4 \times 4$ spatial grid pooling to detect localized motion on wide-angle stationary backgrounds.

---

## 9. Automated Verification

The automated test suite runs deterministically on synthetic and real test suites:
```bash
python -m pytest -v
# 19 passed, 1 warning in 6.00s
```

* `backend/tests/test_analysis.py`: Similarity, optical flow, Laplacian blur variance, failure analysis.
* `backend/tests/test_samplers.py`: Uniform, Perceptual, and Motion-Aware samplers.
* `backend/tests/test_metadata.py`: Video metadata extraction, generator streaming, single-frame extraction.
* `backend/tests/test_api.py`: FastAPI endpoints for upload, background processing, results polling, download, and comparison.
* `backend/tests/test_determinism_and_export.py`: Sampling determinism and JSON experiment reproducibility.

---

## 10. Installation & Running Locally

### Prerequisites
* Python 3.10+ (tested on Python 3.11 - 3.14)
* FFmpeg (installed and available on system `PATH`)

### Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/username/VideoShrink.git
cd VideoShrink

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run validation suite
python experiments/run_validation.py

# 4. Run Pytest suite
pytest backend/tests/ -v
```

### Launching the Application

**Option 1: Streamlit Dashboard (Full UI + Integrated Engine)**
```bash
streamlit run frontend/streamlit_app.py
```
Open your browser at `http://localhost:8501`.

**Option 2: FastAPI REST API Server**
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation is available at `http://localhost:8000/docs`.

**Option 3: Docker Compose (Both Services)**
```bash
docker-compose up --build
```

---

## 11. Railway Deployment

VideoShrink is engineered for direct deployment to [Railway](https://railway.app):
* Containerized with `Dockerfile` including `ffmpeg`, `libgl1`, and system OpenCV headless dependencies.
* Production port binding via `$PORT`.
* All paths parameterized via `backend/app/config.py`.

### Deploying to Railway via Railway CLI:
```bash
railway init
railway up
```

---

## 12. Future Extensions (Roadmap)

1. **PyTorch Downstream Model Benchmark**: Benchmark classification accuracy on Kinetics-400 / UCF-101 using VideoMAE or 3D-ResNet.
2. **Object Detection Temporal Coverage**: Benchmark YOLOv8 / Faster-RCNN bounding-box tracklet continuity on pruned datasets.
3. **Hard-Example Mining**: Prioritize retaining frames where model prediction entropy or loss is high.
4. **Cloud Object Storage (S3 / GCS)**: Swap `LocalStorageBackend` with AWS S3 / GCP Storage backend.
5. **GPU-Accelerated Optical Flow**: Optional CUDA-backed Farneback or NVOF for ultra-high-resolution datasets.
6. **Dataset-Level Batch Processing**: Multi-video directory batch compression with aggregated reduction analytics.

