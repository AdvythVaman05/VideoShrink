import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from backend.app.video.reader import VideoReader

class JobCancelledException(Exception):
    """Raised when a video processing or encoding task is cancelled cooperatively."""
    pass

class VideoWriter:
    """
    Reconstructs an optimized video from selected frame indices.
    Decoupled from frame selection algorithm.
    """
    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")

    def write_selected_frames(
        self,
        source_video_path: str | Path,
        selected_indices: List[int],
        output_video_path: str | Path,
        playback_fps: Optional[float] = None,
        preserve_duration: bool = True,
        cancellation_check: Optional[Any] = None,
    ) -> Path:
        """
        Stream selected frames from source video to output MP4.
        If preserve_duration is True and playback_fps is None, effective_fps is used
        so that output video spans approximately the original duration.
        """
        source_path = Path(source_video_path)
        output_path = Path(output_video_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if cancellation_check and cancellation_check():
            output_path.unlink(missing_ok=True)
            raise JobCancelledException("Video synthesis cancelled before start.")

        reader = VideoReader(source_path)
        meta = reader.get_metadata()

        if not selected_indices:
            raise ValueError("No frames selected for output video.")

        selected_set = set(selected_indices)
        num_selected = len(selected_indices)

        # Calculate playback FPS
        if playback_fps is not None:
            fps = float(playback_fps)
        elif preserve_duration and meta.duration_seconds > 0:
            # Effective FPS to cover same duration
            fps = max(1.0, round(num_selected / meta.duration_seconds, 2))
        else:
            fps = meta.fps

        width, height = meta.width, meta.height

        # Attempt FFmpeg write for guaranteed browser h264/yuv420p playback
        if self.ffmpeg_path:
            try:
                self._write_with_ffmpeg(
                    source_path=source_path,
                    selected_set=selected_set,
                    output_path=output_path,
                    fps=fps,
                    width=width,
                    height=height,
                    cancellation_check=cancellation_check
                )
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            except JobCancelledException:
                # Do NOT fall back to OpenCV if job was cancelled
                output_path.unlink(missing_ok=True)
                raise
            except Exception as e:
                # Remove partial/corrupt file before fallback
                output_path.unlink(missing_ok=True)
                print(f"[VideoWriter] FFmpeg failed with error: {e}. Falling back to OpenCV VideoWriter.")

        # Fallback to OpenCV VideoWriter
        self._write_with_opencv(
            source_path=source_path,
            selected_set=selected_set,
            output_path=output_path,
            fps=fps,
            width=width,
            height=height,
            cancellation_check=cancellation_check
        )
        return output_path

    def _write_with_ffmpeg(
        self,
        source_path: Path,
        selected_set: set[int],
        output_path: Path,
        fps: float,
        width: int,
        height: int,
        cancellation_check: Optional[Any] = None,
    ) -> None:
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",  # Explicitly disable audio for video-only dataset outputs
            str(output_path)
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        cap = cv2.VideoCapture(str(source_path))
        frame_idx = 0
        try:
            while True:
                if cancellation_check and cancellation_check():
                    if proc.stdin and not proc.stdin.closed:
                        try:
                            proc.stdin.close()
                        except Exception:
                            pass
                    proc.terminate()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1.0)
                    output_path.unlink(missing_ok=True)
                    raise JobCancelledException("Video synthesis cancelled by user during FFmpeg encoding.")

                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                if frame_idx in selected_set:
                    try:
                        proc.stdin.write(frame.tobytes())
                    except (BrokenPipeError, OSError):
                        break
                frame_idx += 1
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg exited with code {proc.returncode}: {stderr}")
        finally:
            cap.release()
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    proc.kill()

    def _write_with_opencv(
        self,
        source_path: Path,
        selected_set: set[int],
        output_path: Path,
        fps: float,
        width: int,
        height: int,
        cancellation_check: Optional[Any] = None,
    ) -> None:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        if not out.isOpened():
            raise RuntimeError(f"Failed to initialize cv2.VideoWriter for {output_path}")

        cap = cv2.VideoCapture(str(source_path))
        frame_idx = 0
        try:
            while True:
                if cancellation_check and cancellation_check():
                    out.release()
                    output_path.unlink(missing_ok=True)
                    raise JobCancelledException("Video synthesis cancelled by user during OpenCV encoding.")

                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                if frame_idx in selected_set:
                    out.write(frame)
                frame_idx += 1
        finally:
            cap.release()
            out.release()
