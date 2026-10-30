"""Diagnostic feedback for the existing Improve Quality workflow.

This service does not modify synthetic data. It interprets the real before/after
metrics returned by the existing quality-improvement pipeline and creates
actionable, evidence-based feedback for the UI.
"""
from __future__ import annotations

from typing import Any


METRIC_GUIDANCE = {
    "statistical_similarity": (
        "Review the affected columns' distributions and missing-value handling. "
        "Use marginal matching only where the column-level diagnostics support it."
    ),
    "correlation_score": (
        "Inspect the column-pair correlation diagnostics. Prefer a correlation-aware "
        "generation strategy or targeted regeneration; marginal matching alone may not fix relationships."
    ),
    "correlation_error": (
        "Identify the column pairs contributing most to correlation error and avoid "
        "transformations that independently alter strongly related columns."
    ),
    "ml_utility_score": (
        "Check the selected prediction target, class balance and train/test protocol. "
        "Compare utility by target and avoid tuning solely to a composite score."
    ),
    "business_rule_validity": (
        "Review the failed domain rules and affected records. Apply only rules verified "
        "against the real dataset or explicitly configured by the user."
    ),
    "exact_match_rate": (
        "Review exact-match and near-duplicate diagnostics. Apply privacy filtering, "
        "then re-evaluate utility because privacy filtering can change distributions."
    ),
    "dcr_ratio": (
        "Inspect nearest-neighbour distance diagnostics and disclosure risk. A DCR value "
        "is a diagnostic, not a standalone privacy guarantee."
    ),
    "privacy_score": (
        "Review the privacy evaluator's risk level and component metrics before accepting "
        "the candidate. Do not trade away privacy to increase utility."
    ),
    "completeness_score": (
        "Inspect missingness by column and distinguish structural missing values from "
        "unexpected missingness before applying imputation."
    ),
    "duplicate_row_rate": (
        "Inspect duplicate rows and determine whether they are legitimate repeated events "
        "or accidental duplicates before removing or resampling them."
    ),
    "date_order_violation_rate": (
        "Review the inferred date pairs and confirm that their chronological ordering "
        "matches the dataset's actual business process."
    ),
}


def build_feedback_insights(
    metrics_comparison: list[dict[str, Any]] | None,
    strategies_applied: list[str] | None = None,
    domain_rules_summary: dict[str, Any] | None = None,
    privacy_status: dict[str, Any] | None = None,
    improved_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build diagnostics from existing before/after results without inventing scores."""
    rows = metrics_comparison or []
    findings: list[dict[str, Any]] = []
    recommendations: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        metric = str(row.get("metric") or "").strip().lower()
        status = str(row.get("status") or "not_comparable").lower()
        direction = row.get("direction") or "higher_is_better"
        baseline = row.get("baseline")
        improved = row.get("improved")

        # A metric can improve and still remain below an acceptable working target.
        score_targets = {
            "statistical_similarity": 75.0,
            "correlation_score": 70.0,
            "ml_utility_score": 70.0,
            "business_rule_validity": 95.0,
            "completeness_score": 98.0,
        }
        target = score_targets.get(metric)
        try:
            still_below_target = target is not None and improved is not None and float(improved) < target
        except (TypeError, ValueError):
            still_below_target = False

        if still_below_target and status != "regressed":
            findings.append({
                "metric": metric,
                "label": row.get("label") or metric,
                "status": "below_target",
                "severity": "medium" if float(improved) >= target * 0.85 else "high",
                "baseline": baseline,
                "improved": improved,
                "target": target,
                "message": f"The metric improved to {improved}, but remains below the configured review threshold of {target}.",
            })
            guidance = METRIC_GUIDANCE.get(metric)
            if guidance:
                recommendations.append(guidance)

        if status not in {"regressed", "unchanged"}:
            continue

        if status == "regressed":
            severity = "high" if metric in {
                "exact_match_rate", "privacy_score", "dcr_ratio",
                "business_rule_validity", "correlation_error",
            } else "medium"
            title = f"{row.get('label') or metric} regressed"
            message = (
                f"The value changed from {baseline} to {improved}. "
                f"{'Lower' if direction == 'lower_is_better' else 'Higher'} values are "
                f"{'preferred' if direction == 'lower_is_better' else 'generally preferred'} "
                "for this metric."
            )
            findings.append({
                "metric": metric,
                "label": row.get("label") or metric,
                "status": status,
                "severity": severity,
                "baseline": baseline,
                "improved": improved,
                "message": message,
            })
            guidance = METRIC_GUIDANCE.get(metric)
            if guidance:
                recommendations.append(guidance)
        elif status == "unchanged":
            findings.append({
                "metric": metric,
                "label": row.get("label") or metric,
                "status": status,
                "severity": "low",
                "baseline": baseline,
                "improved": improved,
                "message": "This metric did not materially change during this improvement run.",
            })

    rules = domain_rules_summary or {}
    validity = rules.get("improved_validity_percent")
    if validity is not None:
        try:
            if float(validity) < 95.0:
                findings.append({
                    "metric": "business_rule_validity",
                    "label": "Business-rule validity",
                    "status": "below_target",
                    "severity": "high",
                    "baseline": rules.get("baseline_validity_percent"),
                    "improved": validity,
                    "message": "Some empirically verified or configured business rules are still violated.",
                })
                recommendations.append(
                    "Inspect the individual failed business rules before choosing a constraint or resampling strategy."
                )
        except (TypeError, ValueError):
            pass

    privacy = privacy_status or {}
    if privacy.get("privacy_status") == "error":
        findings.append({
            "metric": "privacy",
            "label": "Privacy evaluation",
            "status": "not_evaluated",
            "severity": "high",
            "message": "Privacy evaluation did not complete. Treat the candidate as unverified until privacy checks succeed.",
        })

    # Surface per-column statistical gaps where the evaluator supplies scores.
    evaluation = improved_evaluation or {}
    statistical = evaluation.get("statistical_similarity") or evaluation
    column_scores = statistical.get("columns") if isinstance(statistical, dict) else None
    weak_columns: list[dict[str, Any]] = []
    if isinstance(column_scores, dict):
        for column_name, details in column_scores.items():
            if not isinstance(details, dict):
                continue
            score = details.get("score")
            try:
                if score is not None and float(score) < 70.0:
                    weak_columns.append({
                        "column": str(column_name),
                        "score": float(score),
                        "column_type": details.get("column_type"),
                    })
            except (TypeError, ValueError):
                continue
    if weak_columns:
        findings.append({
            "metric": "column_level_statistical_similarity",
            "label": "Columns with weak statistical similarity",
            "status": "below_target",
            "severity": "medium",
            "columns": weak_columns[:20],
            "message": "These columns have statistical similarity scores below 70 and should be reviewed individually.",
        })
        recommendations.append(
            "Prioritize the listed columns for distribution, type and missing-value diagnostics instead of applying the same transformation to every column."
        )

    if not recommendations and not findings:
        summary = "No regressions or actionable gaps were detected in the metrics returned by this run."
    elif any(item["severity"] == "high" for item in findings):
        summary = "Review the high-priority findings before using or sharing this synthetic dataset."
    elif any(item.get("status") == "below_target" for item in findings):
        summary = "Some metrics remain below their review thresholds. Check the targeted recommendations before accepting the result."
    else:
        summary = "Review the unchanged metrics to decide whether further improvement is worthwhile."

    # Keep recommendations unique and preserve order.
    recommendations = list(dict.fromkeys(recommendations))
    return {
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "finding_count": len(findings),
        "has_high_priority": any(item["severity"] == "high" for item in findings),
        "strategies_reviewed": strategies_applied or [],
    }
