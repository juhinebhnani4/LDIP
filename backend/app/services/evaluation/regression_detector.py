"""Regression detection for RAGAS evaluation results.

Gap 9: Automated RAGAS Regression — Statistical Regression Detection

Compares current batch evaluation results against the active baseline to
detect quality regressions. Uses per-item comparison for granular detection
(not just aggregate averages, which can hide individual regressions).

Design decisions:
- Per-item comparison: catches regressions masked by aggregate averaging
  (e.g., 1 item drops from 0.9 → 0.3 while 4 others stay at 0.9 — aggregate
  shows 0.78 vs 0.90, but per-item catches the specific failure)
- Three severity levels: OK, WARNING, CRITICAL
- Configurable thresholds (relative drop % and absolute minimum)
- Returns structured report for both logging and API response
- No external dependencies — pure Python, testable
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ItemRegression:
    """Regression info for a single golden dataset item."""

    golden_item_id: str
    question_preview: str
    current_overall: float
    baseline_overall: float
    delta: float  # negative = regression
    relative_change_pct: float  # negative = regression
    severity: str  # "ok", "warning", "critical"
    regressed_metrics: list[str] = field(default_factory=list)


@dataclass
class RegressionReport:
    """Complete regression analysis report.

    This is the single output of regression detection — consumed by:
    1. Celery task for structured logging
    2. API endpoint for admin dashboard
    3. Future: Slack/email alerting
    """

    matter_id: str
    # Aggregate
    current_avg_overall: float
    baseline_avg_overall: float
    aggregate_delta: float
    aggregate_severity: str  # "ok", "warning", "critical"
    # Per-item breakdown
    regressed_items: list[ItemRegression] = field(default_factory=list)
    improved_items: list[ItemRegression] = field(default_factory=list)
    unchanged_items: list[ItemRegression] = field(default_factory=list)
    new_items: list[str] = field(default_factory=list)  # golden items not in baseline
    missing_items: list[str] = field(default_factory=list)  # baseline items not in current
    # Summary
    total_items: int = 0
    regression_count: int = 0
    critical_count: int = 0
    has_regression: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response and structured logging."""
        return {
            "matter_id": self.matter_id,
            "aggregate": {
                "current": round(self.current_avg_overall, 4),
                "baseline": round(self.baseline_avg_overall, 4),
                "delta": round(self.aggregate_delta, 4),
                "severity": self.aggregate_severity,
            },
            "summary": {
                "total_items": self.total_items,
                "regression_count": self.regression_count,
                "critical_count": self.critical_count,
                "improved_count": len(self.improved_items),
                "unchanged_count": len(self.unchanged_items),
                "new_items": len(self.new_items),
                "missing_items": len(self.missing_items),
                "has_regression": self.has_regression,
            },
            "regressed_items": [
                {
                    "golden_item_id": r.golden_item_id,
                    "question": r.question_preview,
                    "current": round(r.current_overall, 4),
                    "baseline": round(r.baseline_overall, 4),
                    "delta": round(r.delta, 4),
                    "change_pct": round(r.relative_change_pct, 1),
                    "severity": r.severity,
                    "regressed_metrics": r.regressed_metrics,
                }
                for r in self.regressed_items
            ],
            "improved_items": [
                {
                    "golden_item_id": i.golden_item_id,
                    "question": i.question_preview,
                    "current": round(i.current_overall, 4),
                    "baseline": round(i.baseline_overall, 4),
                    "delta": round(i.delta, 4),
                }
                for i in self.improved_items
            ],
        }


# =============================================================================
# Regression Detection Logic
# =============================================================================


def detect_regression(
    matter_id: str,
    current_results: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> RegressionReport:
    """Detect regressions between current batch results and active baseline.

    Performs both aggregate and per-item comparison:
    1. Aggregate: compares average overall scores
    2. Per-item: for each golden item present in both, compares individual scores

    Severity levels:
    - OK: score improved or within noise threshold (< warning_threshold relative drop)
    - WARNING: relative drop exceeds warning_threshold (default 10%)
    - CRITICAL: absolute score below critical_threshold (default 0.60)

    Args:
        matter_id: Matter UUID.
        current_results: List of evaluation_results rows from the current batch.
        baseline: Active baseline record (from evaluation_baselines table).

    Returns:
        Structured RegressionReport with per-item and aggregate analysis.
    """
    settings = get_settings()

    # Configurable thresholds — these control sensitivity
    warning_threshold = settings.evaluation_regression_threshold  # 10% relative drop
    critical_score = settings.evaluation_critical_threshold  # Absolute minimum

    # Parse baseline per-item scores
    baseline_per_item: dict[str, dict[str, Any]] = baseline.get("per_item_scores", {})
    baseline_avg = float(baseline.get("avg_overall", 0))

    # Build current per-item map (keyed by golden_item_id)
    current_per_item: dict[str, dict[str, Any]] = {}
    current_scores: list[float] = []

    for r in current_results:
        score = float(r.get("overall_score", 0))
        current_scores.append(score)

        gid = r.get("golden_item_id")
        if gid:
            current_per_item[gid] = {
                "overall": score,
                "faithfulness": r.get("faithfulness"),
                "answer_relevancy": r.get("answer_relevancy"),
                "context_recall": r.get("context_recall"),
                "question": (r.get("question") or "")[:100],
            }

    current_avg = sum(current_scores) / len(current_scores) if current_scores else 0.0
    aggregate_delta = current_avg - baseline_avg

    # Determine aggregate severity
    if baseline_avg > 0:
        relative_drop = (baseline_avg - current_avg) / baseline_avg
        if current_avg < critical_score:
            aggregate_severity = "critical"
        elif relative_drop > warning_threshold:
            aggregate_severity = "warning"
        else:
            aggregate_severity = "ok"
    else:
        aggregate_severity = "ok"

    # Per-item comparison
    report = RegressionReport(
        matter_id=matter_id,
        current_avg_overall=current_avg,
        baseline_avg_overall=baseline_avg,
        aggregate_delta=aggregate_delta,
        aggregate_severity=aggregate_severity,
        total_items=len(current_results),
    )

    # Items in both current and baseline
    all_item_ids = set(current_per_item.keys()) | set(baseline_per_item.keys())
    for gid in all_item_ids:
        curr = current_per_item.get(gid)
        base = baseline_per_item.get(gid)

        if curr and not base:
            report.new_items.append(gid)
            continue
        if base and not curr:
            report.missing_items.append(gid)
            continue

        # Both exist — compare
        curr_score = float(curr["overall"])
        base_score = float(base["overall"])
        delta = curr_score - base_score
        question = curr.get("question", base.get("question", ""))

        # Calculate relative change
        if base_score > 0:
            relative_pct = (delta / base_score) * 100
        else:
            relative_pct = 0.0

        # Determine per-item severity
        regressed_metrics: list[str] = []
        if curr_score < critical_score:
            severity = "critical"
        elif base_score > 0 and (base_score - curr_score) / base_score > warning_threshold:
            severity = "warning"
        else:
            severity = "ok"

        # Check individual metrics for regression
        for metric in ("faithfulness", "answer_relevancy", "context_recall"):
            curr_val = curr.get(metric)
            base_val = base.get(metric)
            if curr_val is not None and base_val is not None and base_val > 0:
                metric_drop = (base_val - curr_val) / base_val
                if metric_drop > warning_threshold:
                    regressed_metrics.append(metric)

        item_reg = ItemRegression(
            golden_item_id=gid,
            question_preview=question,
            current_overall=curr_score,
            baseline_overall=base_score,
            delta=delta,
            relative_change_pct=relative_pct,
            severity=severity,
            regressed_metrics=regressed_metrics,
        )

        if severity in ("warning", "critical"):
            report.regressed_items.append(item_reg)
            report.regression_count += 1
            if severity == "critical":
                report.critical_count += 1
        elif delta > 0.01:  # Meaningful improvement (not just noise)
            report.improved_items.append(item_reg)
        else:
            report.unchanged_items.append(item_reg)

    report.has_regression = (
        report.regression_count > 0 or aggregate_severity != "ok"
    )

    # Log result
    if report.has_regression:
        logger.warning(
            "regression_detected",
            matter_id=matter_id,
            aggregate_severity=aggregate_severity,
            current_avg=round(current_avg, 4),
            baseline_avg=round(baseline_avg, 4),
            regression_count=report.regression_count,
            critical_count=report.critical_count,
            regressed_items=[r.golden_item_id for r in report.regressed_items],
        )
    else:
        logger.info(
            "no_regression",
            matter_id=matter_id,
            current_avg=round(current_avg, 4),
            baseline_avg=round(baseline_avg, 4),
            improved_count=len(report.improved_items),
        )

    return report
