import os
import subprocess
from pathlib import Path
import requests

OUTPUT_DIR = Path("experiments/test_videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master"

VIDEOS = {
    "raw_talking_head.mp4": f"{BASE_URL}/head-pose-face-detection-female.mp4",
    "raw_classroom.mp4": f"{BASE_URL}/classroom.mp4",
    "raw_traffic.mp4": f"{BASE_URL}/person-bicycle-car-detection.mp4",
    "raw_walking.mp4": f"{BASE_URL}/face-demographics-walking.mp4",
}

def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Already downloaded: {dest.name}")
        return
    print(f"Downloading {dest.name} from {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    print(f"Downloaded {dest.name} ({dest.stat().st_size / (1024*1024):.2f} MB)")

def trim_video(src: Path, dest: Path, start_sec: float = 0.0, duration_sec: float = 8.0) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Already prepared: {dest.name}")
        return
    print(f"Trimming {src.name} -> {dest.name} ({duration_sec}s)...")
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", str(src),
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        str(dest)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Prepared {dest.name} ({dest.stat().st_size / (1024*1024):.2f} MB)")

def create_multi_scene_video(clip1: Path, clip2: Path, clip3: Path, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Already prepared: {dest.name}")
        return
    print(f"Creating multi-scene video {dest.name}...")
    # Concatenate 3s of each using ffmpeg filter_complex
    cmd = [
        "ffmpeg", "-y",
        "-ss", "1.0", "-t", "3.0", "-i", str(clip1),
        "-ss", "1.0", "-t", "3.0", "-i", str(clip2),
        "-ss", "1.0", "-t", "3.0", "-i", str(clip3),
        "-filter_complex",
        "[0:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];"
        "[1:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];"
        "[2:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[v]",
        "-map", "[v]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(dest)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Prepared {dest.name} ({dest.stat().st_size / (1024*1024):.2f} MB)")

def main():
    # 1. Download raw sources
    raw_files = {}
    for name, url in VIDEOS.items():
        dest = OUTPUT_DIR / name
        download_file(url, dest)
        raw_files[name] = dest

    # 2. Prepare 5 distinct test videos
    v_a = OUTPUT_DIR / "video_a_talking_head.mp4"
    trim_video(raw_files["raw_talking_head.mp4"], v_a, start_sec=2.0, duration_sec=8.0)

    v_b = OUTPUT_DIR / "video_b_lecture_presentation.mp4"
    trim_video(raw_files["raw_classroom.mp4"], v_b, start_sec=1.0, duration_sec=8.0)

    v_c = OUTPUT_DIR / "video_c_fast_action.mp4"
    trim_video(raw_files["raw_traffic.mp4"], v_c, start_sec=0.0, duration_sec=8.0)

    v_d = OUTPUT_DIR / "video_d_outdoor_movement.mp4"
    trim_video(raw_files["raw_walking.mp4"], v_d, start_sec=1.0, duration_sec=8.0)

    v_e = OUTPUT_DIR / "video_e_multi_scene_cuts.mp4"
    create_multi_scene_video(v_a, v_c, v_b, v_e)

    print("\nAll 5 real-world test videos prepared in experiments/test_videos/:")
    for f in sorted(OUTPUT_DIR.glob("video_*.mp4")):
        print(f" - {f.name} ({f.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    main()
