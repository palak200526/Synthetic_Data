import pandas as pd
import numpy as np


def detect_arithmetic_relationships(
    dataframe: pd.DataFrame,
    threshold: float = 1.0,
):
    """
    Detect deterministic arithmetic relationships
    between numerical columns.

    Supported:
        A + B = C
        A - B = C
        A * B = C
        A / B = C
    """

    rules = []

    numerical_columns = dataframe.select_dtypes(
        include="number"
    ).columns.tolist()

    if len(numerical_columns) < 3:
        return rules

    for target in numerical_columns:

        for left_index in range(
            len(numerical_columns)
        ):

            left = numerical_columns[left_index]

            if left == target:
                continue

            for right_index in range(
                left_index + 1,
                len(numerical_columns)
            ):

                right = numerical_columns[right_index]

                if right == target:
                    continue

                left_values = dataframe[left]
                right_values = dataframe[right]
                target_values = dataframe[target]

                # ------------------------------------------
                # A + B = C
                # ------------------------------------------

                predicted = (
                    left_values + right_values
                )

                accuracy = np.isclose(
                    predicted,
                    target_values,
                    rtol=1e-5,
                    atol=1e-2,
                    equal_nan=False,
                ).mean()

                if accuracy >= threshold:
                    rules.append({
                        "target": target,
                        "operation": "add",
                        "operands": [left, right],
                        "accuracy": float(accuracy),
                    })

                # ------------------------------------------
                # A - B = C
                # ------------------------------------------

                predicted = (
                    left_values - right_values
                )

                accuracy = np.isclose(
                    predicted,
                    target_values,
                    rtol=1e-5,
                    atol=1e-2,
                    equal_nan=False,
                ).mean()

                if accuracy >= threshold:
                    rules.append({
                        "target": target,
                        "operation": "subtract",
                        "operands": [left, right],
                        "accuracy": float(accuracy),
                    })

                # ------------------------------------------
                # B - A = C
                # ------------------------------------------

                predicted = (
                    right_values - left_values
                )

                accuracy = np.isclose(
                    predicted,
                    target_values,
                    rtol=1e-5,
                    atol=1e-2,
                    equal_nan=False,
                ).mean()

                if accuracy >= threshold:
                    rules.append({
                        "target": target,
                        "operation": "subtract",
                        "operands": [right, left],
                        "accuracy": float(accuracy),
                    })

                # ------------------------------------------
                # A * B = C
                # ------------------------------------------

                predicted = (
                    left_values * right_values
                )

                accuracy = np.isclose(
                    predicted,
                    target_values,
                    rtol=1e-5,
                    atol=1e-2,
                    equal_nan=False,
                ).mean()

                if accuracy >= threshold:
                    rules.append({
                        "target": target,
                        "operation": "multiply",
                        "operands": [left, right],
                        "accuracy": float(accuracy),
                    })

                # ------------------------------------------
                # A / B = C
                # ------------------------------------------

                non_zero = right_values != 0

                if non_zero.any():

                    predicted = (
                        left_values[non_zero]
                        / right_values[non_zero]
                    )

                    accuracy = np.isclose(
                        predicted,
                        target_values[non_zero],
                        rtol=1e-5,
                        atol=1e-2,
                        equal_nan=False,
                    ).mean()

                    if accuracy >= threshold:
                        rules.append({
                            "target": target,
                            "operation": "divide",
                            "operands": [left, right],
                            "accuracy": float(accuracy),
                        })

    return rules


def apply_business_rules(
    dataframe: pd.DataFrame,
    rules: list,
) -> pd.DataFrame:

    result = dataframe.copy()

    for rule in rules:

        target = rule["target"]
        operation = rule["operation"]
        left, right = rule["operands"]

        if (
            left not in result.columns
            or right not in result.columns
        ):
            continue

        if operation == "add":

            result[target] = (
                result[left] + result[right]
            )

        elif operation == "subtract":

            result[target] = (
                result[left] - result[right]
            )

        elif operation == "multiply":

            result[target] = (
                result[left] * result[right]
            )

        elif operation == "divide":

            non_zero = result[right] != 0

            result.loc[non_zero, target] = (
                result.loc[non_zero, left]
                / result.loc[non_zero, right]
            )

        # Preserve integer type when possible
        if target in result.columns:

            if pd.api.types.is_integer_dtype(
                dataframe[target]
            ):
                result[target] = (
                    result[target]
                    .round()
                    .astype(int)
                )

    return result