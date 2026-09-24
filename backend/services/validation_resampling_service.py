import pandas as pd

from backend.services.validation_engine import validate_dataframe


def generate_valid_rows(
    generate_function,
    target_row_count: int,
    rules: list[dict],
    max_attempts: int = 10,
):
    """
    Generate synthetic rows repeatedly until the required
    number of valid rows is collected.

    Invalid rows are rejected and additional rows are generated.
    No invalid row is corrected or modified.
    """

    if target_row_count <= 0:
        raise ValueError(
            "target_row_count must be greater than 0."
        )

    if not callable(generate_function):
        raise ValueError(
            "generate_function must be callable."
        )

    valid_batches = []
    total_valid_rows = 0
    total_generated_rows = 0
    total_rejected_rows = 0

    validation_history = []

    for attempt in range(1, max_attempts + 1):

        remaining_rows = (
            target_row_count - total_valid_rows
        )

        if remaining_rows <= 0:
            break

        # Generate extra rows to compensate for
        # rows rejected by validation rules.
        
        batch_size = remaining_rows

        generated_dataframe = generate_function(
            batch_size
        )

        if not isinstance(
            generated_dataframe,
            pd.DataFrame,
        ):
            raise TypeError(
                "generate_function must return a pandas DataFrame."
            )

        # Ensure the generator does not return
        # more rows than requested for this batch.
        if len(generated_dataframe) > batch_size:
            generated_dataframe = generated_dataframe.head(
                batch_size
            )

        total_generated_rows += len(
            generated_dataframe
        )

        validation_result = validate_dataframe(
            generated_dataframe,
            rules,
        )

        invalid_indices = set(
            validation_result["invalid_rows"]
        )

        valid_dataframe = (
            generated_dataframe.drop(
                index=list(invalid_indices),
                errors="ignore",
            )
        )

        rejected_count = (
            len(generated_dataframe)
            - len(valid_dataframe)
        )

        total_rejected_rows += rejected_count
        total_valid_rows += len(valid_dataframe)

        if not valid_dataframe.empty:
            valid_batches.append(
                valid_dataframe
            )

        validation_history.append({
            "attempt": attempt,
            "generated_rows": len(
                generated_dataframe
            ),
            "valid_rows": len(
                valid_dataframe
            ),
            "rejected_rows": rejected_count,
            "validation": validation_result,
        })

    if total_valid_rows < target_row_count:
        raise RuntimeError(
            "Unable to generate the required number "
            "of valid rows within the maximum attempts. "
            f"Required: {target_row_count}, "
            f"Valid: {total_valid_rows}, "
            f"Attempts: {max_attempts}."
        )

    final_dataframe = (
        pd.concat(
            valid_batches,
            ignore_index=True,
        )
        .head(target_row_count)
    )

    final_validation = validate_dataframe(
        final_dataframe,
        rules,
    )

    if not final_validation["valid"]:
        raise RuntimeError(
            "Final synthetic dataset still contains "
            "validation violations."
        )

    return {
        "dataframe": final_dataframe,
        "target_row_count": target_row_count,
        "total_generated_rows": total_generated_rows,
        "total_valid_rows": len(final_dataframe),
        "total_rejected_rows": total_rejected_rows,
        "attempts": len(validation_history),
        "validation_history": validation_history,
        "final_validation": final_validation,
    }