import pandas as pd


def validate_non_negative(
    dataframe: pd.DataFrame,
    column: str,
):
    if column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{column}' not found.",
        }

    invalid_mask = dataframe[column] < 0

    return {
        "valid": not invalid_mask.any(),
        "invalid_rows": dataframe.index[invalid_mask].tolist(),
        "error": None,
    }


def validate_not_null(
    dataframe: pd.DataFrame,
    column: str,
):
    if column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{column}' not found.",
        }

    invalid_mask = dataframe[column].isna()

    return {
        "valid": not invalid_mask.any(),
        "invalid_rows": dataframe.index[invalid_mask].tolist(),
        "error": None,
    }


def validate_range(
    dataframe: pd.DataFrame,
    column: str,
    minimum=None,
    maximum=None,
):
    if column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{column}' not found.",
        }

    invalid_mask = pd.Series(
        False,
        index=dataframe.index,
    )

    if minimum is not None:
        invalid_mask |= dataframe[column] < minimum

    if maximum is not None:
        invalid_mask |= dataframe[column] > maximum

    return {
        "valid": not invalid_mask.any(),
        "invalid_rows": dataframe.index[invalid_mask].tolist(),
        "error": None,
    }


def validate_allowed_values(
    dataframe: pd.DataFrame,
    column: str,
    allowed_values: list,
):
    if column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{column}' not found.",
        }

    invalid_mask = ~dataframe[column].isin(
        allowed_values
    )

    return {
        "valid": not invalid_mask.any(),
        "invalid_rows": dataframe.index[invalid_mask].tolist(),
        "error": None,
    }


def validate_date_order(
    dataframe: pd.DataFrame,
    start_column: str,
    end_column: str,
):
    if start_column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{start_column}' not found.",
        }

    if end_column not in dataframe.columns:
        return {
            "valid": False,
            "invalid_rows": [],
            "error": f"Column '{end_column}' not found.",
        }

    start_dates = pd.to_datetime(
        dataframe[start_column],
        errors="coerce",
    )

    end_dates = pd.to_datetime(
        dataframe[end_column],
        errors="coerce",
    )

    invalid_mask = (
        start_dates.notna()
        & end_dates.notna()
        & (end_dates < start_dates)
    )

    return {
        "valid": not invalid_mask.any(),
        "invalid_rows": dataframe.index[invalid_mask].tolist(),
        "error": None,
    }


def validate_rule(
    dataframe: pd.DataFrame,
    rule: dict,
):
    rule_type = rule["rule_type"]
    definition = rule["rule_definition"]

    if rule_type == "non_negative":
        return validate_non_negative(
            dataframe,
            definition["column"],
        )

    if rule_type == "not_null":
        return validate_not_null(
            dataframe,
            definition["column"],
        )

    if rule_type == "range":
        return validate_range(
            dataframe,
            definition["column"],
            definition.get(
                "minimum",
                definition.get("min")
            ),
            definition.get(
                "maximum",
                definition.get("max")
            ),
        )

    if rule_type == "allowed_values":
        return validate_allowed_values(
            dataframe,
            definition["column"],
            definition["allowed_values"],
        )

    if rule_type == "date_order":
        return validate_date_order(
            dataframe,
            definition["start_column"],
            definition["end_column"],
        )

    return {
        "valid": False,
        "invalid_rows": [],
        "error": f"Unsupported rule type: {rule_type}",
    }


def validate_dataframe(
    dataframe: pd.DataFrame,
    rules: list[dict],
):
    results = []

    all_invalid_indices = set()

    for rule in rules:

        if not rule.get("is_active", True):
            continue

        result = validate_rule(
            dataframe,
            rule,
        )

        invalid_indices = result["invalid_rows"]

        all_invalid_indices.update(
            invalid_indices
        )

        results.append({
            "rule_id": rule["rule_id"],
            "rule_name": rule["rule_name"],
            "rule_type": rule["rule_type"],
            "valid": result["valid"],
            "invalid_row_count": len(
                invalid_indices
            ),
            "invalid_rows": invalid_indices,
            "error": result["error"],
        })

    return {
        "valid": len(all_invalid_indices) == 0,
        "valid_row_count": len(dataframe)
        - len(all_invalid_indices),
        "invalid_row_count": len(all_invalid_indices),
        "invalid_rows": sorted(
            all_invalid_indices
        ),
        "rules": results,
    }