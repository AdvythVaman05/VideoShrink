from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SensitiveSegment:
    start_sec: float
    end_sec: float
    start_time_formatted: str
    end_time_formatted: str
    reasons: List[str]
    severity: str  # "high", "medium", "low"
    recommendation: str

def format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

class FailureAnalyzer:
    """
    Identifies video segments where aggressive frame pruning
    risks losing critical computer-vision information.
    """
    def __init__(
        self,
        high_motion_threshold: float = 0.55,
        blur_ratio_threshold: float = 0.6,
        merge_gap_sec: float = 1.0
    ):
        self.high_motion_threshold = high_motion_threshold
        self.blur_ratio_threshold = blur_ratio_threshold
        self.merge_gap_sec = merge_gap_sec

    def analyze_timeline(
        self,
        timeline_data: List[Dict[str, Any]]
    ) -> List[SensitiveSegment]:
        """
        Scan per-frame analysis records and identify sensitive clusters.
        timeline_data: list of dicts with keys:
            timestamp, motion_score, is_scene_cut, is_blurry, is_underexposed, is_overexposed
        """
        if not timeline_data:
            return []

        flagged_points: List[tuple[float, str, str]] = []  # (timestamp, reason, severity)

        for item in timeline_data:
            ts = item.get("timestamp", 0.0)
            motion = item.get("motion_score", 0.0)
            is_cut = item.get("is_scene_cut", False)
            is_blurry = item.get("is_blurry", False)
            is_dark = item.get("is_underexposed", False)
            is_bright = item.get("is_overexposed", False)

            if is_cut:
                flagged_points.append((ts, "Abrupt scene transition", "high"))
            elif motion > self.high_motion_threshold:
                flagged_points.append((ts, "High motion / rapid camera movement", "high"))
            elif is_blurry:
                flagged_points.append((ts, "Significant motion blur detected", "medium"))
            elif is_dark or is_bright:
                flagged_points.append((ts, "Extreme exposure / lighting anomaly", "medium"))

        if not flagged_points:
            return []

        # Group into contiguous segments
        segments: List[SensitiveSegment] = []
        curr_start = flagged_points[0][0]
        curr_end = flagged_points[0][0]
        curr_reasons = {flagged_points[0][1]}
        curr_severity = flagged_points[0][2]

        for ts, reason, severity in flagged_points[1:]:
            if ts - curr_end <= self.merge_gap_sec:
                curr_end = ts
                curr_reasons.add(reason)
                if severity == "high":
                    curr_severity = "high"
            else:
                # Close current segment
                segments.append(
                    self._create_segment(curr_start, curr_end, list(curr_reasons), curr_severity)
                )
                curr_start = ts
                curr_end = ts
                curr_reasons = {reason}
                curr_severity = severity

        # Close trailing segment
        segments.append(
            self._create_segment(curr_start, curr_end, list(curr_reasons), curr_severity)
        )

        return segments

    def _create_segment(
        self,
        start_sec: float,
        end_sec: float,
        reasons: List[str],
        severity: str
    ) -> SensitiveSegment:
        # Ensure at least 0.5s window
        if end_sec - start_sec < 0.5:
            end_sec = start_sec + 0.5

        if severity == "high":
            rec = "Consider lowering motion sensitivity or increasing minimum FPS to preserve training dynamics."
        else:
            rec = "Review sampled frames to verify downstream feature fidelity."

        return SensitiveSegment(
            start_sec=round(start_sec, 2),
            end_sec=round(end_sec, 2),
            start_time_formatted=format_time(start_sec),
            end_time_formatted=format_time(end_sec),
            reasons=reasons,
            severity=severity,
            recommendation=rec
        )
