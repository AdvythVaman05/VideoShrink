from backend.app.evaluation.metrics import ReductionMetrics
from backend.app.evaluation.benchmark import (
    VisualPreservationProxyResult,
    VisualPreservationProxyEvaluator,
    DownstreamMLBenchmark,
    PyTorchBenchmarkPhase2Stub,
)
from backend.app.evaluation.comparison import StrategyComparator

__all__ = [
    "ReductionMetrics",
    "VisualPreservationProxyResult",
    "VisualPreservationProxyEvaluator",
    "DownstreamMLBenchmark",
    "PyTorchBenchmarkPhase2Stub",
    "StrategyComparator",
]
