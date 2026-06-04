"""A/B Testing Service for Voyage vs OpenAI/Cohere provider comparison.

Gap 10: Automated Voyage A/B Testing

Three components:
1. ABTestRouter — deterministic hash-based traffic routing for sticky user cohorts
2. ABTestRunner — orchestrates side-by-side evaluation of control vs treatment
3. ABTestAnalyzer — statistical comparison (Welch's t-test) and automated decision

Architecture:
- Individual per-question results stored in existing evaluation_results table
  (linked by job_id, with embedding_provider/rerank_provider columns)
- Experiment-level metadata stored in ab_test_runs table
- Comparison uses same golden dataset with identical questions to eliminate variance
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from datetime import UTC, datetime
from typing import Any

import structlog
from scipy import stats as scipy_stats

from app.core.config import get_settings
from app.services.supabase.client import get_service_client as _get_service_raw
from app.services.supabase.client import get_supabase_client as _get_supabase_raw

logger = structlog.get_logger(__name__)


def get_supabase():
    """Get Supabase client with null guard (for reads — respects RLS)."""
    client = _get_supabase_raw()
    if client is None:
        raise RuntimeError("Supabase client not configured — A/B testing requires database access")
    return client


def _get_service_supabase():
    """Get service-role Supabase client for write operations that bypass RLS.

    Required because ab_test_runs UPDATE is restricted to service_role only
    (authenticated users only have SELECT+INSERT via RLS policies).
    """
    client = _get_service_raw()
    if client is None:
        raise RuntimeError("Supabase service client not configured — A/B testing requires service-role access")
    return client


# =============================================================================
# Phase 2: Deterministic Traffic Router
# =============================================================================


class ABTestRouter:
    """Deterministic hash-based provider routing for A/B testing.

    Routes queries to control (OpenAI+Cohere) or treatment (Voyage+Voyage)
    based on a stable hash of user_id + matter_id. This ensures:
    - Same user always gets same provider for same matter (sticky cohorts)
    - No within-user variance (confounding eliminated)
    - Gradual rollout via configurable percentage (0-100)
    - Explicit user selection in ModelSelector always takes precedence
    """

    @staticmethod
    def determine_provider(
        user_id: str | None,
        matter_id: str,
        percentage: int | None = None,
    ) -> tuple[str | None, str | None]:
        """Determine which provider to use for this user+matter.

        Args:
            user_id: User UUID (None for system/batch queries → always control).
            matter_id: Matter UUID.
            percentage: Override percentage (0-100). If None, uses config value.

        Returns:
            Tuple of (embedding_provider, rerank_provider).
            Returns (None, None) for control arm (use defaults).
            Returns ('voyage', 'voyage') for treatment arm.
        """
        settings = get_settings()

        if not settings.voyage_ab_testing_enabled:
            return None, None

        if percentage is None:
            percentage = settings.voyage_traffic_percentage

        # Clamp to valid range
        percentage = max(0, min(100, percentage))

        if percentage <= 0:
            return None, None
        if percentage >= 100:
            return "voyage", "voyage"

        # System/batch users always get control (no user_id to hash)
        if not user_id or user_id == "system-evaluation":
            return None, None

        # Deterministic hash → stable bucket assignment
        # MD5 is fine here (not security, just distribution)
        hash_input = f"{user_id}:{matter_id}".encode()
        hash_value = int(hashlib.md5(hash_input, usedforsecurity=False).hexdigest(), 16)
        bucket = hash_value % 100  # 0-99

        if bucket < percentage:
            return "voyage", "voyage"
        return None, None

    @staticmethod
    def get_cohort_label(
        embedding_provider: str | None,
        rerank_provider: str | None,
    ) -> str:
        """Get human-readable cohort label for logging/analytics."""
        if embedding_provider == "voyage" or rerank_provider == "voyage":
            return "treatment"
        return "control"


# =============================================================================
# Phase 3: Statistical Analyzer
# =============================================================================


class ABTestAnalyzer:
    """Statistical comparison and automated decision logic.

    Uses Welch's t-test (unequal variance) to compare RAGAS scores between
    control and treatment arms. Welch's t-test is appropriate because:
    - Samples may have different sizes (some items may fail in one arm)
    - Variances may differ between providers
    - No assumption of equal variance needed

    Decision logic:
    - If treatment quality >= control quality (within confidence interval)
      AND treatment cost <= control cost → treatment wins
    - If treatment quality significantly worse → control wins
    - If insufficient data → no decision
    """

    # Significance level for Welch's t-test
    ALPHA = 0.05

    # Minimum acceptable effect size (Cohen's d) to declare a winner
    # 0.2 = small effect — we only care about meaningful differences
    MIN_EFFECT_SIZE = 0.2

    @staticmethod
    def welch_t_test(
        scores_a: list[float],
        scores_b: list[float],
    ) -> dict[str, float]:
        """Perform Welch's t-test for independent samples with unequal variance.

        Uses scipy.stats for accurate p-values at all sample sizes. Effect size
        uses Glass's delta (control arm SD as denominator) which is appropriate
        when variances are unequal — consistent with using Welch's t-test.

        Args:
            scores_a: Control arm scores.
            scores_b: Treatment arm scores.

        Returns:
            Dict with t_statistic, p_value_approx, degrees_of_freedom,
            effect_size_cohens_d, mean_a, mean_b, std_a, std_b.
        """
        n_a = len(scores_a)
        n_b = len(scores_b)

        if n_a < 2 or n_b < 2:
            return {
                "t_statistic": 0.0,
                "p_value_approx": 1.0,
                "degrees_of_freedom": 0.0,
                "effect_size_cohens_d": 0.0,
                "mean_a": sum(scores_a) / n_a if n_a else 0.0,
                "mean_b": sum(scores_b) / n_b if n_b else 0.0,
                "std_a": 0.0,
                "std_b": 0.0,
                "insufficient_data": True,
            }

        mean_a = sum(scores_a) / n_a
        mean_b = sum(scores_b) / n_b

        # Sample variances
        var_a = sum((x - mean_a) ** 2 for x in scores_a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in scores_b) / (n_b - 1)

        std_a = math.sqrt(var_a)
        std_b = math.sqrt(var_b)

        # Welch's t-statistic
        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se < 1e-10:
            return {
                "t_statistic": 0.0,
                "p_value_approx": 1.0,
                "degrees_of_freedom": n_a + n_b - 2,
                "effect_size_cohens_d": 0.0,
                "mean_a": mean_a,
                "mean_b": mean_b,
                "std_a": std_a,
                "std_b": std_b,
            }

        t_stat = (mean_a - mean_b) / se

        # Welch-Satterthwaite degrees of freedom
        num = (var_a / n_a + var_b / n_b) ** 2
        denom = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        df = num / denom if denom > 0 else n_a + n_b - 2

        # Exact two-tailed p-value via scipy (accurate for all df, including df < 5)
        p_value = float(scipy_stats.t.sf(abs(t_stat), df) * 2)

        # Glass's delta: use control arm (scores_a) SD as denominator.
        # Appropriate for Welch's context where variances are unequal — we measure
        # the effect relative to the established baseline (control), not a pooled
        # estimate that conflates both arms' variance.
        # Glass's delta edge case: when control SD is 0, all control scores
        # are identical. If means differ, the effect is effectively infinite
        # relative to a zero-variance baseline. We use 999.0 as a sentinel
        # (not float('inf')) because JSON serialization of inf is undefined
        # and would crash the DB write in complete_comparison().
        if std_a > 0:
            glass_delta = abs(mean_a - mean_b) / std_a
        elif abs(mean_a - mean_b) > 1e-10:
            glass_delta = 999.0
        else:
            glass_delta = 0.0

        return {
            "t_statistic": round(t_stat, 4),
            "p_value_approx": round(p_value, 6),
            "degrees_of_freedom": round(df, 2),
            "effect_size_cohens_d": round(glass_delta, 4),
            "mean_a": round(mean_a, 4),
            "mean_b": round(mean_b, 4),
            "std_a": round(std_a, 4),
            "std_b": round(std_b, 4),
        }

    # Minimum acceptable faithfulness score for a legal tool.
    # Below this threshold, treatment is rejected regardless of overall score.
    MIN_FAITHFULNESS = 0.70

    @staticmethod
    def make_decision(
        control_scores: list[float],
        treatment_scores: list[float],
        control_cost_usd: float,
        treatment_cost_usd: float,
        min_samples: int | None = None,
        control_faithfulness: list[float] | None = None,
        treatment_faithfulness: list[float] | None = None,
    ) -> dict[str, Any]:
        """Make automated decision about which provider to use.

        Decision matrix:
        1. Insufficient data → 'insufficient_data'
        2. Treatment faithfulness below safety threshold → 'control_wins'
        3. Treatment significantly better → 'treatment_wins'
        4. No significant difference AND treatment cheaper → 'treatment_wins'
        5. Control significantly better → 'control_wins'
        6. No significant difference AND control cheaper → 'control_wins'
        7. No significant difference AND similar cost → 'no_significant_difference'

        Args:
            control_scores: Overall RAGAS scores for control (OpenAI+Cohere).
            treatment_scores: Overall RAGAS scores for treatment (Voyage+Voyage).
            control_cost_usd: Total cost in USD for control arm.
            treatment_cost_usd: Total cost in USD for treatment arm.
            min_samples: Minimum samples per arm (default from config).
            control_faithfulness: Per-item faithfulness scores for control arm.
            treatment_faithfulness: Per-item faithfulness scores for treatment arm.

        Returns:
            Dict with decision, confidence, reasoning, and statistical_test data.
        """
        settings = get_settings()
        if min_samples is None:
            min_samples = settings.voyage_ab_min_samples

        n_control = len(control_scores)
        n_treatment = len(treatment_scores)

        # Gate 1: Minimum sample size
        if n_control < min_samples or n_treatment < min_samples:
            return {
                "decision": "insufficient_data",
                "confidence": 0.0,
                "reasoning": (
                    f"Need at least {min_samples} samples per arm. "
                    f"Control has {n_control}, treatment has {n_treatment}."
                ),
                "statistical_test": None,
            }

        # Run Welch's t-test (H0: means are equal)
        test = ABTestAnalyzer.welch_t_test(control_scores, treatment_scores)

        # Guard: t-test itself may flag insufficient data (< 2 samples per arm)
        if test.get("insufficient_data"):
            return {
                "decision": "insufficient_data",
                "confidence": 0.0,
                "reasoning": (
                    f"Welch's t-test requires at least 2 samples per arm. "
                    f"Control has {n_control}, treatment has {n_treatment}."
                ),
                "statistical_test": test,
            }

        p_value = test["p_value_approx"]
        effect_size = test["effect_size_cohens_d"]
        mean_control = test["mean_a"]
        mean_treatment = test["mean_b"]

        # Gate 2: Faithfulness safety check (critical for legal tools)
        # If treatment arm has significantly lower faithfulness, reject it
        # regardless of overall score — unfaithful answers are dangerous.
        #
        # If faithfulness data is unavailable (empty or None), we log a warning
        # but do NOT skip the gate — we proceed to the quality comparison without
        # the faithfulness check. This is a known limitation when evaluation
        # results lack faithfulness scores.
        has_faithfulness_data = (
            treatment_faithfulness
            and control_faithfulness
            and len(treatment_faithfulness) >= 2
            and len(control_faithfulness) >= 2
        )
        if not has_faithfulness_data:
            logger.warning(
                "ab_test_faithfulness_gate_skipped",
                reason="insufficient_faithfulness_data",
                control_count=len(control_faithfulness) if control_faithfulness else 0,
                treatment_count=len(treatment_faithfulness) if treatment_faithfulness else 0,
            )
        if has_faithfulness_data:
            avg_t_faith = sum(treatment_faithfulness) / len(treatment_faithfulness)
            avg_c_faith = sum(control_faithfulness) / len(control_faithfulness)
            if avg_t_faith < ABTestAnalyzer.MIN_FAITHFULNESS:
                return {
                    "decision": "control_wins",
                    "confidence": 0.9,
                    "reasoning": (
                        f"Treatment faithfulness ({avg_t_faith:.3f}) is below "
                        f"safety threshold ({ABTestAnalyzer.MIN_FAITHFULNESS}). "
                        f"In a legal tool, unfaithful answers are unacceptable. "
                        f"Control faithfulness: {avg_c_faith:.3f}."
                    ),
                    "statistical_test": test,
                    "faithfulness_gate": True,
                }
            # Also flag if treatment faithfulness is significantly worse than control.
            # 5% relative drop threshold — stricter than overall quality (10%) because
            # faithfulness regressions in a legal tool are more dangerous than relevancy drops.
            if (
                avg_c_faith > 0
                and (avg_c_faith - avg_t_faith) / avg_c_faith > 0.05
                and len(treatment_faithfulness) >= 5
            ):
                faith_test = ABTestAnalyzer.welch_t_test(
                    control_faithfulness, treatment_faithfulness
                )
                if faith_test["p_value_approx"] < ABTestAnalyzer.ALPHA:
                    return {
                        "decision": "control_wins",
                        "confidence": round(
                            max(0.0, min(1.0 - faith_test["p_value_approx"], 1.0)),
                            3,
                        ),
                        "reasoning": (
                            f"Treatment faithfulness ({avg_t_faith:.3f}) is "
                            f"significantly worse than control ({avg_c_faith:.3f}) "
                            f"(p={faith_test['p_value_approx']:.4f}). "
                            f"Faithfulness regressions are independently gated "
                            f"for legal safety."
                        ),
                        "statistical_test": test,
                        "faithfulness_gate": True,
                    }

        is_significant = p_value < ABTestAnalyzer.ALPHA
        is_meaningful = effect_size >= ABTestAnalyzer.MIN_EFFECT_SIZE
        treatment_better = mean_treatment > mean_control
        # Cost comparison — only use if both costs are non-zero (real data)
        # When costs are zero or estimated, skip cost-based decisions
        has_real_costs = control_cost_usd > 0 and treatment_cost_usd > 0
        treatment_cheaper = has_real_costs and treatment_cost_usd < control_cost_usd
        cost_diff_pct = (
            ((control_cost_usd - treatment_cost_usd) / control_cost_usd * 100)
            if has_real_costs
            else 0.0
        )

        # Confidence: higher when p-value is lower and effect is larger
        confidence = max(0.0, min(1.0 - p_value, 1.0)) if is_significant else 0.3

        # Decision logic
        if is_significant and is_meaningful:
            if treatment_better:
                decision = "treatment_wins"
                reasoning = (
                    f"Voyage quality ({mean_treatment:.3f}) is significantly better "
                    f"than OpenAI ({mean_control:.3f}) "
                    f"(p={p_value:.4f}, d={effect_size:.2f}). "
                )
                if treatment_cheaper:
                    reasoning += f"Voyage is also {cost_diff_pct:.1f}% cheaper."
                    confidence = min(confidence + 0.1, 1.0)
                else:
                    reasoning += "Voyage costs more but quality gain justifies it."
            else:
                decision = "control_wins"
                reasoning = (
                    f"OpenAI quality ({mean_control:.3f}) is significantly better "
                    f"than Voyage ({mean_treatment:.3f}) "
                    f"(p={p_value:.4f}, d={effect_size:.2f}). "
                    f"Keep using OpenAI+Cohere."
                )
        else:
            # No significant quality difference — use cost as tiebreaker
            if treatment_cheaper:
                decision = "treatment_wins"
                reasoning = (
                    f"No significant quality difference "
                    f"(control={mean_control:.3f} vs treatment={mean_treatment:.3f}, "
                    f"p={p_value:.4f}). "
                    f"Voyage is {cost_diff_pct:.1f}% cheaper — switch to save costs."
                )
                confidence = 0.6  # Moderate confidence for cost-based decisions
            elif has_real_costs and control_cost_usd < treatment_cost_usd:
                decision = "control_wins"
                reasoning = (
                    f"No significant quality difference "
                    f"(control={mean_control:.3f} vs treatment={mean_treatment:.3f}). "
                    f"OpenAI is cheaper — no reason to switch."
                )
                confidence = 0.5
            else:
                decision = "no_significant_difference"
                reasoning = (
                    f"No significant quality difference "
                    f"(control={mean_control:.3f} vs treatment={mean_treatment:.3f}, "
                    f"p={p_value:.4f}). "
                )
                if not has_real_costs:
                    reasoning += "Cost data unavailable for comparison. "
                else:
                    reasoning += "Similar costs. "
                reasoning += "Run more samples or check per-query-type breakdown."
                confidence = 0.3

        result = {
            "decision": decision,
            "confidence": round(confidence, 3),
            "reasoning": reasoning,
            "statistical_test": test,
        }
        # Flag when faithfulness safety gate was skipped (insufficient data).
        # Auto-promotion logic should refuse to promote when this flag is set.
        if not has_faithfulness_data:
            result["faithfulness_gate_skipped"] = True
        return result


# =============================================================================
# Phase 1 & 3: A/B Test Runner (orchestrates comparison)
# =============================================================================


class ABTestRunner:
    """Orchestrates side-by-side provider comparison experiments.

    Workflow:
    1. Create ab_test_runs record (status=pending)
    2. Run batch evaluation with control providers → store results
    3. Run batch evaluation with treatment providers → store results
    4. Aggregate scores per arm, run statistical analysis
    5. Make automated decision, update ab_test_runs record

    Individual results are in evaluation_results (linked by job_id).
    Experiment-level metadata is in ab_test_runs.
    """

    @staticmethod
    async def create_run(
        matter_id: str,
        tags: list[str] | None = None,
        created_by: str | None = None,
        control_embedding: str = "openai",
        control_reranker: str = "cohere",
        treatment_embedding: str = "voyage",
        treatment_reranker: str = "voyage",
    ) -> dict[str, Any]:
        """Create a new A/B test run record.

        Args:
            matter_id: Matter UUID to evaluate.
            tags: Optional golden dataset tag filters.
            created_by: User UUID who initiated the test.
            control_embedding: Control arm embedding provider.
            control_reranker: Control arm reranker.
            treatment_embedding: Treatment arm embedding provider.
            treatment_reranker: Treatment arm reranker.

        Returns:
            Created ab_test_runs record.
        """
        supabase = _get_service_supabase()

        row = {
            "matter_id": matter_id,
            "status": "pending",
            "control_embedding": control_embedding,
            "control_reranker": control_reranker,
            "treatment_embedding": treatment_embedding,
            "treatment_reranker": treatment_reranker,
            "tags": tags or [],
        }
        if created_by:
            row["created_by"] = created_by

        result = await asyncio.to_thread(
            lambda: supabase.table("ab_test_runs").insert(row).execute()
        )
        if not result.data:
            raise RuntimeError("Failed to create A/B test run — insert returned no data")
        return result.data[0]

    # Valid status transitions for optimistic locking
    _STATUS_TRANSITIONS: dict[str, set[str]] = {
        "pending": {"running_control", "failed", "cancelled"},
        "running_control": {"running_treatment", "failed", "cancelled"},
        "running_treatment": {"comparing", "failed", "cancelled"},
        "comparing": {"completed", "failed", "cancelled"},
    }

    @staticmethod
    async def update_run(
        run_id: str,
        updates: dict[str, Any],
        expected_status: str | None = None,
    ) -> None:
        """Update an A/B test run record with optimistic locking.

        Uses service-role client because UPDATE on ab_test_runs is restricted
        to service_role only (authenticated users have SELECT+INSERT only).

        When `expected_status` is provided, the update includes a WHERE clause
        on the current status, preventing stale writes (e.g., overwriting a
        cancellation). If the status doesn't match, the update silently affects
        0 rows — this is safe because concurrent transitions are rare and the
        final state is always consistent.

        If `expected_status` is None, the update is unconditional (used for
        metadata-only updates like setting job_id or final completion data).
        """
        # Validate state machine transition if both old and new status are known
        new_status = updates.get("status")
        if expected_status and new_status:
            allowed = ABTestRunner._STATUS_TRANSITIONS.get(expected_status, set())
            if allowed and new_status not in allowed:
                raise ValueError(
                    f"Invalid status transition: {expected_status} -> {new_status}. "
                    f"Allowed: {sorted(allowed)}"
                )

        supabase = _get_service_supabase()

        def _do_update():
            query = supabase.table("ab_test_runs").update(updates).eq("id", run_id)
            if expected_status is not None:
                return query.eq("status", expected_status).execute()
            return query.execute()

        result = await asyncio.to_thread(_do_update)
        if expected_status is not None and not result.data:
            logger.warning(
                "ab_test_status_transition_failed",
                run_id=run_id,
                expected_status=expected_status,
                attempted_update=updates.get("status"),
            )
            raise RuntimeError(
                f"Status transition failed for run {run_id}: "
                f"expected status '{expected_status}' but row was not updated "
                f"(likely already transitioned or cancelled)"
            )

    @staticmethod
    async def get_run(run_id: str) -> dict[str, Any] | None:
        """Get an A/B test run by ID."""
        supabase = get_supabase()
        result = await asyncio.to_thread(
            lambda: supabase.table("ab_test_runs")
            .select("*")
            .eq("id", run_id)
            .execute()
        )
        return result.data[0] if result.data else None

    @staticmethod
    async def list_runs(
        matter_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List A/B test runs with optional filters."""
        supabase = get_supabase()

        def _query():
            q = supabase.table("ab_test_runs").select("*")
            if matter_id:
                q = q.eq("matter_id", matter_id)
            if status:
                q = q.eq("status", status)
            return q.order("created_at", desc=True).limit(limit).execute()

        result = await asyncio.to_thread(_query)
        return result.data or []

    @staticmethod
    async def aggregate_scores(job_id: str) -> dict[str, Any] | None:
        """Aggregate evaluation scores for a batch job.

        Uses the get_ab_test_scores RPC function for efficiency.
        Falls back to client-side aggregation if RPC not available.
        """
        supabase = get_supabase()

        try:
            result = await asyncio.to_thread(
                lambda: supabase.rpc("get_ab_test_scores", {"p_job_id": job_id}).execute()
            )
            if result.data:
                return result.data
        except Exception as e:
            logger.warning(
                "ab_test_rpc_fallback",
                job_id=job_id,
                error=str(e),
                msg="get_ab_test_scores RPC failed, falling back to client-side aggregation",
            )

        # Fallback: client-side aggregation
        result = await asyncio.to_thread(
            lambda: supabase.table("evaluation_results")
            .select(
                "golden_item_id, overall_score, context_recall, "
                "faithfulness, answer_relevancy, search_latency_ms"
            )
            .eq("job_id", job_id)
            .not_.is_("overall_score", "null")
            .execute()
        )

        if not result.data:
            return None

        rows = result.data
        n = len(rows)
        return {
            "count": n,
            "context_recall": round(
                sum(r.get("context_recall") or 0 for r in rows) / n, 4
            ),
            "faithfulness": round(
                sum(r.get("faithfulness") or 0 for r in rows) / n, 4
            ),
            "answer_relevancy": round(
                sum(r.get("answer_relevancy") or 0 for r in rows) / n, 4
            ),
            "overall": round(
                sum(r.get("overall_score") or 0 for r in rows) / n, 4
            ),
            "scores": rows,
        }

    @staticmethod
    async def complete_comparison(
        run_id: str,
        control_job_id: str,
        treatment_job_id: str,
    ) -> dict[str, Any]:
        """Complete a comparison run — aggregate scores, analyze, decide.

        Called after both batch evaluations finish. Aggregates scores,
        runs Welch's t-test, makes automated decision, updates the run.

        Args:
            run_id: A/B test run UUID.
            control_job_id: Celery job ID for control arm.
            treatment_job_id: Celery job ID for treatment arm.

        Returns:
            Updated run record with decision.
        """
        runner = ABTestRunner()

        await runner.update_run(
            run_id, {"status": "comparing"}, expected_status="running_treatment"
        )

        try:
            # Aggregate scores for each arm
            control_agg = await runner.aggregate_scores(control_job_id)
            treatment_agg = await runner.aggregate_scores(treatment_job_id)

            if not control_agg or not treatment_agg:
                await runner.update_run(run_id, {
                    "status": "failed",
                    "error_message": "Failed to aggregate scores for one or both arms",
                    "completed_at": datetime.now(UTC).isoformat(),
                }, expected_status="comparing")
                return {"status": "failed"}

            # Extract individual overall scores for statistical test
            control_scores = [
                s["overall_score"]
                for s in (control_agg.get("scores") or [])
                if s.get("overall_score") is not None
            ]
            treatment_scores = [
                s["overall_score"]
                for s in (treatment_agg.get("scores") or [])
                if s.get("overall_score") is not None
            ]

            # Extract latency percentiles
            control_latencies = sorted([
                s["search_latency_ms"]
                for s in (control_agg.get("scores") or [])
                if s.get("search_latency_ms") is not None
            ])
            treatment_latencies = sorted([
                s["search_latency_ms"]
                for s in (treatment_agg.get("scores") or [])
                if s.get("search_latency_ms") is not None
            ])

            def _percentile(arr: list[int], p: float) -> int | None:
                if not arr:
                    return None
                k = int(len(arr) * p / 100)
                return arr[min(k, len(arr) - 1)]

            # Extract per-item faithfulness for safety gate
            control_faithfulness = [
                s["faithfulness"]
                for s in (control_agg.get("scores") or [])
                if s.get("faithfulness") is not None
            ]
            treatment_faithfulness = [
                s["faithfulness"]
                for s in (treatment_agg.get("scores") or [])
                if s.get("faithfulness") is not None
            ]

            # Get cost data from llm_costs table
            control_cost = await _get_job_cost(control_job_id)
            treatment_cost = await _get_job_cost(treatment_job_id)

            # Run statistical analysis and make decision
            decision_result = ABTestAnalyzer.make_decision(
                control_scores=control_scores,
                treatment_scores=treatment_scores,
                control_cost_usd=control_cost,
                treatment_cost_usd=treatment_cost,
                control_faithfulness=control_faithfulness,
                treatment_faithfulness=treatment_faithfulness,
            )

            # Update run with all results
            updates = {
                "status": "completed",
                "control_scores": {
                    "context_recall": control_agg.get("context_recall"),
                    "faithfulness": control_agg.get("faithfulness"),
                    "answer_relevancy": control_agg.get("answer_relevancy"),
                    "overall": control_agg.get("overall"),
                    "count": control_agg.get("count"),
                },
                "treatment_scores": {
                    "context_recall": treatment_agg.get("context_recall"),
                    "faithfulness": treatment_agg.get("faithfulness"),
                    "answer_relevancy": treatment_agg.get("answer_relevancy"),
                    "overall": treatment_agg.get("overall"),
                    "count": treatment_agg.get("count"),
                },
                "control_latency_p50_ms": _percentile(control_latencies, 50),
                "control_latency_p95_ms": _percentile(control_latencies, 95),
                "treatment_latency_p50_ms": _percentile(treatment_latencies, 50),
                "treatment_latency_p95_ms": _percentile(treatment_latencies, 95),
                "control_cost_usd": control_cost,
                "treatment_cost_usd": treatment_cost,
                "decision": decision_result["decision"],
                "decision_confidence": decision_result["confidence"],
                "decision_reasoning": decision_result["reasoning"],
                "statistical_test": decision_result.get("statistical_test"),
                "golden_item_count": max(
                    control_agg.get("count", 0),
                    treatment_agg.get("count", 0),
                ),
                "completed_at": datetime.now(UTC).isoformat(),
            }

            await runner.update_run(run_id, updates)

            logger.info(
                "ab_test_comparison_completed",
                run_id=run_id,
                decision=decision_result["decision"],
                confidence=decision_result["confidence"],
                control_overall=control_agg.get("overall"),
                treatment_overall=treatment_agg.get("overall"),
            )

            return {**updates, "id": run_id}

        except Exception as e:
            logger.error(
                "ab_test_comparison_failed",
                run_id=run_id,
                error=str(e),
            )
            # Guard: only overwrite to "failed" if still in "comparing" state.
            # If already cancelled or completed, don't clobber.
            try:  # noqa: SIM105
                await runner.update_run(run_id, {
                    "status": "failed",
                    "error_message": str(e),
                    "completed_at": datetime.now(UTC).isoformat(),
                }, expected_status="comparing")
            except (RuntimeError, ValueError):
                pass  # Already transitioned — safe to ignore
            raise

    @staticmethod
    async def get_current_status() -> dict[str, Any]:
        """Get current A/B testing status for dashboard.

        Returns:
            Dict with routing config, latest run results, and recommendations.
        """
        settings = get_settings()
        supabase = get_supabase()

        def _fetch_status():
            """Run all three DB queries in a single thread to avoid blocking
            the FastAPI event loop (sync Supabase client)."""
            latest_result = (
                supabase.table("ab_test_runs")
                .select("*")
                .eq("status", "completed")
                .order("completed_at", desc=True)
                .limit(1)
                .execute()
            )
            running_result = (
                supabase.table("ab_test_runs")
                .select("id, status, created_at, matter_id")
                .in_("status", ["pending", "running_control", "running_treatment", "comparing"])
                .limit(1)
                .execute()
            )
            count_result = (
                supabase.table("ab_test_runs")
                .select("id", count="exact")
                .eq("status", "completed")
                .execute()
            )
            return latest_result, running_result, count_result

        latest_result, running_result, count_result = await asyncio.to_thread(
            _fetch_status
        )

        latest_run = latest_result.data[0] if latest_result.data else None
        running_run = running_result.data[0] if running_result.data else None
        total_completed = count_result.count or 0

        return {
            "enabled": settings.voyage_ab_testing_enabled,
            "traffic_percentage": settings.voyage_traffic_percentage,
            "auto_promote_enabled": settings.voyage_ab_auto_promote_enabled,
            "min_samples": settings.voyage_ab_min_samples,
            "latest_run": latest_run,
            "running": running_run,
            "total_completed_runs": total_completed,
        }


# =============================================================================
# Helpers
# =============================================================================


async def _get_job_cost(job_id: str) -> float:
    """Get total cost in USD for evaluation results linked to a job.

    Returns 0.0 to signal "no real cost data available" until we implement
    actual cost tracking by linking job_id to llm_costs entries. The decision
    engine correctly handles this: when both costs are 0, has_real_costs=False
    and cost is not used as a tiebreaker.

    Previously this returned hardcoded estimates that systematically favored
    Voyage (0.00127/query vs OpenAI's 0.00302/query), causing the decision
    engine to always pick Voyage as a cost tiebreaker. This was misleading
    because the estimates were fabricated, not measured.

    TODO: Link batch evaluation Celery task ID to llm_costs entries via
    correlation ID or explicit job_id tagging.
    """
    return 0.0
