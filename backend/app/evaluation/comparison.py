from typing import List, Dict, Any, Optional
from backend.app.video.reader import VideoReader
from backend.app.sampling.selector import FrameSelector
from backend.app.evaluation.benchmark import VisualPreservationProxyEvaluator

class StrategyComparator:
    """
    Runs multiple frame selection strategies on a single video
    and generates a comparative benchmark summary.
    """
    @classmethod
    def compare_strategies(
        cls,
        reader: VideoReader,
        strategies: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs baseline uniform, perceptual, and motion-aware strategies.
        Returns tabular comparison records with proxy preservation metrics.
        """
        if strategies is None:
            strategies = [
                {"name": "uniform", "params": {"target_fps": 10.0}},
                {"name": "perceptual", "params": {"similarity_threshold": 0.96}},
                {"name": "motion_aware", "params": {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0}},
            ]

        evaluator = VisualPreservationProxyEvaluator()
        comparison_results = []

        for strat in strategies:
            s_name = strat["name"]
            s_params = strat.get("params", {})

            result = FrameSelector.run_selection(s_name, reader, s_params)
            proxy_result = evaluator.evaluate(reader, result)

            comparison_results.append({
                "strategy": s_name,
                "parameters": s_params,
                "total_frames": result.total_frames,
                "selected_frames": result.selected_count,
                "retention_pct": round(result.retention_rate * 100.0, 2),
                "reduction_pct": round(result.reduction_rate * 100.0, 2),
                "effective_fps": round(result.effective_fps, 2),
                "processing_time_sec": round(result.processing_time_sec, 2),
                "visual_preservation_proxy_score": proxy_result.proxy_fidelity_score,
                "motion_coverage_score": proxy_result.motion_coverage_score,
                "temporal_coverage_score": proxy_result.temporal_coverage_score,
                "metric_label": "Visual/Data Preservation Proxy (Heuristic)",
            })

        return comparison_results
