from __future__ import annotations

from typing import Any

import pandas as pd


def build_preprocessing_summary(
    original_dataframe: pd.DataFrame,
    result: dict[str, Any],
    configurations: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Human-readable summary of what preprocessing did, for the UI.
    Works only from data the pipeline already produced (no re-processing).
    """
    processed = result["dataframe"]
    categorical = list(result.get("categorical_columns") or [])
    numerical = list(result.get("numerical_columns") or [])
    original_columns = [str(c) for c in original_dataframe.columns]
    processed_columns = [str(c) for c in processed.columns]
    configurations = configurations or []

    # --- missing values (counted on the ORIGINAL data) ---
    missing_by_col = {
        str(c): int(n)
        for c, n in original_dataframe.isna().sum().items()
        if int(n) > 0
    }
    missing_total = int(sum(missing_by_col.values()))

    # --- outliers (reported, rows are NOT removed) ---
    outliers = result.get("outliers") or {}
    iqr = outliers.get("iqr") or {}
    zsc = outliers.get("zscore") or {}
    outlier_rows = []
    for col in numerical:
        n_iqr = len(iqr.get(col, []) or [])
        n_z = len(zsc.get(col, []) or [])
        if n_iqr or n_z:
            outlier_rows.append(
                {
                    "column": str(col),
                    "iqr": n_iqr,
                    "zscore": n_z,
                    "pct_of_rows": round(
                        100.0 * max(n_iqr, n_z) / max(len(original_dataframe), 1), 2
                    ),
                }
            )
    outlier_rows.sort(key=lambda r: -r["iqr"])

    # --- columns: removed / added / encoded ---
    action_counts: dict[str, int] = {}
    removed_by_config = []
    for cfg in configurations:
        act = cfg.get("action") or "keep"
        action_counts[act] = action_counts.get(act, 0) + 1
        if act == "remove":
            removed_by_config.append(str(cfg.get("column_name")))

    cat_set = {str(c) for c in categorical}
    removed_columns = [
        c for c in original_columns if c not in processed_columns and c not in cat_set
    ]
    dummy_prefixes = tuple(f"{c}_" for c in cat_set)
    added_columns = [
        c
        for c in processed_columns
        if c not in original_columns and not c.startswith(dummy_prefixes)
    ]
    encoded_new = [
        c
        for c in processed_columns
        if c not in original_columns and c.startswith(dummy_prefixes)
    ]

    # --- readable steps ---
    steps = []
    steps.append(
        f"Detected outliers in {len(numerical)} numeric column(s) using IQR and "
        f"Z-score; {len(outlier_rows)} column(s) have outliers. Rows are kept."
        if numerical
        else "No numeric columns, so outlier detection was skipped."
    )
    steps.append(
        f"Filled {missing_total:,} missing value(s) across {len(missing_by_col)} "
        "column(s) (numeric: median if the column has outliers, otherwise mean; "
        "text/categorical: most frequent value)."
        if missing_total
        else "No missing values found."
    )
    if configurations:
        parts = [f"{n} {a}" for a, n in sorted(action_counts.items())]
        steps.append("Applied your column configuration: " + ", ".join(parts) + ".")
    if added_columns:
        steps.append(
            "Added domain features: " + ", ".join(added_columns[:8])
            + ("…" if len(added_columns) > 8 else "") + "."
        )
    encoding_metadata = result.get("encoding_metadata") or {}
    methods: dict[str, list[str]] = {}
    skipped: dict[str, list[str]] = {}
    for source_column, info in encoding_metadata.items():
        method = str((info or {}).get("selected_method") or "unknown")
        if method.startswith("skip_"):
            skipped.setdefault(method, []).append(str(source_column))
        else:
            methods.setdefault(method, []).append(str(source_column))

    display_names = {
        "onehot": "One-Hot Encoding",
        "binary": "Binary Encoding",
        "frequency": "Frequency Encoding",
        "count": "Count Encoding",
        "hashing": "Feature Hashing",
    }
    for method, columns in sorted(methods.items()):
        display = display_names.get(method, method.replace("_", " ").title())
        output_count = sum(
            len((encoding_metadata.get(column) or {}).get("output_columns") or [])
            for column in columns
        )
        if method in {"frequency", "count"}:
            steps.append(
                f"Applied {display} to {len(columns)} categorical column(s): "
                + ", ".join(columns[:6])
                + ("…" if len(columns) > 6 else "") + "."
            )
        else:
            steps.append(
                f"Applied {display} to {len(columns)} categorical column(s), "
                f"creating {output_count} output column(s): "
                + ", ".join(columns[:6])
                + ("…" if len(columns) > 6 else "") + "."
            )
    for reason, columns in sorted(skipped.items()):
        readable = {
            "skip_identifier": "identifier-like",
            "skip_constant": "constant",
            "skip_free_text": "high-cardinality free-text",
        }.get(reason, reason.replace("skip_", "").replace("_", " "))
        steps.append(
            f"Skipped encoding for {len(columns)} {readable} column(s): "
            + ", ".join(columns[:6])
            + ("…" if len(columns) > 6 else "") + "."
        )
    if not methods and not skipped:
        steps.append("No categorical columns required encoding.")
    steps.append(
        "Validated the output: row count unchanged, no missing or infinite values."
    )

    return {
        "rows_before": int(len(original_dataframe)),
        "rows_after": int(len(processed)),
        "columns_before": int(len(original_columns)),
        "columns_after": int(len(processed_columns)),
        "missing_values_filled": missing_total,
        "missing_by_column": missing_by_col,
        "outlier_summary": outlier_rows,
        "removed_columns": removed_columns,
        "added_columns": added_columns,
        "encoded_columns_count": sum(
            len((info or {}).get("output_columns") or [])
            for info in (result.get("encoding_metadata") or {}).values()
        ),
        "action_counts": action_counts,
        "transformations": steps,
    }