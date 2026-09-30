import pandas as pd

from backend.services.business_rule_detector import (
    detect_arithmetic_relationships,
    apply_business_rules,
)


def test_detect_subtraction_relationship():

    dataframe = pd.DataFrame({
        "quantity_on_hand": [100, 200, 300],
        "quantity_reserved": [20, 50, 100],
        "quantity_available": [80, 150, 200],
    })

    rules = detect_arithmetic_relationships(
        dataframe
    )

    matching_rules = [
        rule
        for rule in rules
        if (
            rule["target"] == "quantity_available"
            and rule["operation"] == "subtract"
            and rule["operands"]
            == [
                "quantity_on_hand",
                "quantity_reserved",
            ]
        )
    ]

    assert len(matching_rules) > 0
    assert matching_rules[0]["accuracy"] == 1.0

def test_no_relationship_returns_empty_list():

    dataframe = pd.DataFrame({
        "sales": [100, 250, 390],
        "cost": [40, 80, 120],
        "quantity": [7, 12, 19],
    })

    rules = detect_arithmetic_relationships(
        dataframe
    )

    assert rules == []

def test_detect_addition_relationship():

    dataframe = pd.DataFrame({
        "a": [10, 20, 30],
        "b": [5, 15, 25],
        "total": [15, 35, 55],
    })

    rules = detect_arithmetic_relationships(
        dataframe
    )

    assert any(
        rule["target"] == "total"
        and rule["operation"] == "add"
        and rule["accuracy"] == 1.0
        for rule in rules
    )


def test_detect_multiplication_relationship():

    dataframe = pd.DataFrame({
        "quantity": [2, 3, 5],
        "price": [10, 20, 30],
        "amount": [20, 60, 150],
    })

    rules = detect_arithmetic_relationships(
        dataframe
    )

    assert any(
        rule["target"] == "amount"
        and rule["operation"] == "multiply"
        and rule["accuracy"] == 1.0
        for rule in rules
    )


def test_detect_division_relationship():

    dataframe = pd.DataFrame({
        "total": [20, 60, 150],
        "quantity": [2, 3, 5],
        "price": [10, 20, 30],
    })

    rules = detect_arithmetic_relationships(
        dataframe
    )

    assert any(
        rule["target"] == "price"
        and rule["operation"] == "divide"
        and rule["accuracy"] == 1.0
        for rule in rules
    )

def test_apply_subtraction_rule():

    dataframe = pd.DataFrame({
        "quantity_on_hand": [100, 200],
        "quantity_reserved": [20, 50],
        "quantity_available": [999, 999],
    })

    rules = [
        {
            "target": "quantity_available",
            "operation": "subtract",
            "operands": [
                "quantity_on_hand",
                "quantity_reserved",
            ],
            "accuracy": 1.0,
        }
    ]

    result = apply_business_rules(
        dataframe,
        rules,
    )

    assert result["quantity_available"].tolist() == [
        80,
        150,
    ]

def validate_business_rules(
    dataframe: pd.DataFrame,
    rules: list,
    threshold: float = 1.0,
) -> dict:
    """
    Validate whether the generated dataframe
    still satisfies the detected business rules.
    """

    results = []

    for rule in rules:

        target = rule["target"]
        operation = rule["operation"]
        left, right = rule["operands"]

        required_columns = {
            target,
            left,
            right,
        }

        if not required_columns.issubset(
            dataframe.columns
        ):
            results.append({
                "target": target,
                "operation": operation,
                "valid": False,
                "accuracy": 0.0,
                "error": "Required columns are missing.",
            })
            continue

        if operation == "add":
            expected = (
                dataframe[left]
                + dataframe[right]
            )

        elif operation == "subtract":
            expected = (
                dataframe[left]
                - dataframe[right]
            )

        elif operation == "multiply":
            expected = (
                dataframe[left]
                * dataframe[right]
            )

        elif operation == "divide":

            non_zero = dataframe[right] != 0

            expected = pd.Series(
                index=dataframe.index,
                dtype=float,
            )

            expected.loc[non_zero] = (
                dataframe.loc[non_zero, left]
                / dataframe.loc[non_zero, right]
            )

        else:
            continue

        actual = dataframe[target]

        valid_rows = expected.eq(actual)

        accuracy = valid_rows.mean()

        results.append({
            "target": target,
            "operation": operation,
            "operands": [left, right],
            "valid": accuracy >= threshold,
            "accuracy": float(accuracy),
        })

    overall_valid = all(
        result["valid"]
        for result in results
    ) if results else True

    return {
        "valid": overall_valid,
        "rules_checked": len(results),
        "results": results,
    }

def test_validate_business_rule():

    dataframe = pd.DataFrame({
        "quantity_on_hand": [100, 200],
        "quantity_reserved": [20, 50],
        "quantity_available": [80, 150],
    })

    rules = [
        {
            "target": "quantity_available",
            "operation": "subtract",
            "operands": [
                "quantity_on_hand",
                "quantity_reserved",
            ],
            "accuracy": 1.0,
        }
    ]

    result = validate_business_rules(
        dataframe,
        rules,
    )

    assert result["valid"] is True
    assert result["rules_checked"] == 1
    assert result["results"][0]["accuracy"] == 1.0