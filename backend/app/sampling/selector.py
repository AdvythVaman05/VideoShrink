from typing import Dict, Any, Optional, Callable
from backend.app.video.reader import VideoReader
from backend.app.sampling.base import BaseSampler, SelectionResult
from backend.app.sampling.uniform import UniformSampler
from backend.app.sampling.perceptual import PerceptualSampler
from backend.app.sampling.motion_aware import MotionAwareSampler

class FrameSelector:
    """
    Factory and orchestrator for frame sampling strategies.
    """
    @staticmethod
    def get_sampler(strategy_name: str, params: Optional[Dict[str, Any]] = None) -> BaseSampler:
        params = params or {}
        strat = strategy_name.lower().strip()

        if strat in ("uniform", "baseline"):
            return UniformSampler(
                target_fps=params.get("target_fps"),
                stride=params.get("stride")
            )
        elif strat in ("perceptual", "similarity"):
            return PerceptualSampler(
                similarity_threshold=params.get("similarity_threshold", 0.96),
                max_interval_sec=params.get("max_interval_sec", 2.5)
            )
        elif strat in ("motion", "motion_aware", "scene_aware"):
            return MotionAwareSampler(
                motion_sensitivity=params.get("motion_sensitivity", 0.5),
                min_fps=params.get("min_fps", 2.0),
                max_fps=params.get("max_fps", 15.0),
                scene_cut_threshold=params.get("scene_cut_threshold", 0.40)
            )
        else:
            raise ValueError(f"Unknown sampling strategy: '{strategy_name}'. Supported: uniform, perceptual, motion_aware")

    @classmethod
    def run_selection(
        cls,
        strategy_name: str,
        reader: VideoReader,
        params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SelectionResult:
        sampler = cls.get_sampler(strategy_name, params)
        return sampler.sample(reader, progress_callback=progress_callback)
