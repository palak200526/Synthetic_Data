import pandas as pd


def apply_new_ids(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Generate new unique values for identifier columns.

    Original identifier values are completely replaced.
    """

    dataframe = dataframe.copy()

    for column in columns:

        if column not in dataframe.columns:
            continue

        dataframe[column] = [
            f"{column}_{index:06d}"
            for index in range(1, len(dataframe) + 1)
        ]

    return dataframe


def apply_remove(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Remove columns configured with the remove action.
    """

    dataframe = dataframe.copy()

    existing_columns = [
        column
        for column in columns
        if column in dataframe.columns
    ]

    if existing_columns:
        dataframe = dataframe.drop(
            columns=existing_columns
        )

    return dataframe


def apply_generalize(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Apply generalization to configured columns.

    Generalization depends on the type and business meaning
    of the column. Since the current configuration schema does
    not contain a specific generalization rule, the original
    values are preserved for now.

    This function is kept as a separate processing step so that
    domain-specific generalization rules can be added later.
    """

    dataframe = dataframe.copy()

    for column in columns:

        if column not in dataframe.columns:
            continue

        # No generic transformation is applied yet.
        # Generalization rules will be added when the
        # configuration contains explicit instructions.

        dataframe[column] = dataframe[column]

    return dataframe


def apply_derived(
    dataframe: pd.DataFrame,
    configurations: list[dict],
) -> pd.DataFrame:
    """
    Generate derived columns using configured rules.

    Supported operations:
        add
        subtract
        multiply
        divide
    """

    dataframe = dataframe.copy()

    for config in configurations:

        column_name = config["column_name"]
        rule = config.get("rule")

        if not rule:
            raise ValueError(
                f"Derived column '{column_name}' "
                "requires a rule."
            )

        operation = rule.get("operation")
        operands = rule.get("operands", [])

        if len(operands) < 2:
            raise ValueError(
                f"Derived column '{column_name}' "
                "requires at least two operands."
            )

        # Make sure all operands exist
        missing_operands = [
            operand
            for operand in operands
            if operand not in dataframe.columns
        ]

        if missing_operands:
            raise ValueError(
                f"Cannot create derived column "
                f"'{column_name}'. Missing operands: "
                f"{missing_operands}"
            )

        # Start with the first operand
        result = dataframe[operands[0]]

        # Apply operation sequentially
        for operand in operands[1:]:

            if operation == "add":
                result = result + dataframe[operand]

            elif operation == "subtract":
                result = result - dataframe[operand]

            elif operation == "multiply":
                result = result * dataframe[operand]

            elif operation == "divide":

                denominator = dataframe[operand]

                # Avoid division by zero
                result = result.div(
                    denominator.replace(0, pd.NA)
                )

            else:
                raise ValueError(
                    f"Unsupported derived operation "
                    f"'{operation}' for column "
                    f"'{column_name}'."
                )

        dataframe[column_name] = result

    return dataframe


def apply_column_actions(
    dataframe: pd.DataFrame,
    grouped_actions: dict,
    configurations: list[dict],
) -> pd.DataFrame:
    """
    Apply configured column actions to generated data.

    Processing order:

    1. Generate new identifiers
    2. Generalize columns
    3. Generate derived columns
    4. Remove columns
    """

    dataframe = dataframe.copy()

    # ---------------------------------------------------------
    # 1. Generate new identifiers
    # ---------------------------------------------------------

    dataframe = apply_new_ids(
        dataframe,
        grouped_actions.get("new_id", []),
    )

    # ---------------------------------------------------------
    # 2. Generalize configured columns
    # ---------------------------------------------------------

    dataframe = apply_generalize(
        dataframe,
        grouped_actions.get("generalize", []),
    )

    # ---------------------------------------------------------
    # 3. Generate derived columns
    # ---------------------------------------------------------

    derived_configurations = [
        config
        for config in configurations
        if config.get("action") == "derived"
    ]

    dataframe = apply_derived(
        dataframe,
        derived_configurations,
    )

    # ---------------------------------------------------------
    # 4. Remove configured columns
    # ---------------------------------------------------------

    dataframe = apply_remove(
        dataframe,
        grouped_actions.get("remove", []),
    )

    return dataframe