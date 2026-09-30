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

    Invalid rows are rejected and replacement rows are generated.
    Invalid rows are never corrected or modified.
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

    rows_to_generate = target_row_count

    for attempt in range(1, max_attempts + 1):

        # Stop once enough valid rows have been collected.
        if total_valid_rows >= target_row_count:
            break

        # ---------------------------------------------------------
        # Generate rows
        # ---------------------------------------------------------
        generated_dataframe = generate_function(
            rows_to_generate
        )

        if not isinstance(
            generated_dataframe,
            pd.DataFrame,
        ):
            raise TypeError(
                "generate_function must return a pandas DataFrame."
            )

        # Never accept more rows than requested.
        generated_dataframe = (
            generated_dataframe
            .head(rows_to_generate)
            .copy()
        )

        generated_count = len(
            generated_dataframe
        )

        total_generated_rows += generated_count

        # ---------------------------------------------------------
        # Validate generated rows
        # ---------------------------------------------------------
        validation_result = validate_dataframe(
            generated_dataframe,
            rules,
        )

        invalid_indices = set(
            validation_result["invalid_rows"]
        )

        valid_dataframe = generated_dataframe.drop(
            index=list(invalid_indices),
            errors="ignore",
        )

        valid_count = len(
            valid_dataframe
        )

        rejected_count = (
            generated_count - valid_count
        )

        total_valid_rows += valid_count
        total_rejected_rows += rejected_count

        if not valid_dataframe.empty:
            valid_batches.append(
                valid_dataframe
            )

        validation_history.append({
            "attempt": attempt,
            "generated_rows": generated_count,
            "valid_rows": valid_count,
            "rejected_rows": rejected_count,
            "validation": validation_result,
        })

        # ---------------------------------------------------------
        # Calculate remaining rows
        # ---------------------------------------------------------
        remaining_rows = (
            target_row_count - total_valid_rows
        )

        if remaining_rows <= 0:
            break

        # ---------------------------------------------------------
        # Prepare next generation batch
        # ---------------------------------------------------------
        if valid_count == 0:
            # The entire retry batch failed validation.
            #
            # Do not keep generating the exact same tiny batch.
            # Increase the batch size so that the generator gets
            # enough opportunity to produce valid rows.
            rows_to_generate = max(
                remaining_rows * 2,
                10,
            )
        else:
            # Normally generate only the rows still required.
            rows_to_generate = remaining_rows

    # -------------------------------------------------------------
    # Final check
    # -------------------------------------------------------------
    if total_valid_rows < target_row_count:
        raise RuntimeError(
            "Unable to generate the required number "
            "of valid rows within the maximum attempts. "
            f"Required: {target_row_count}, "
            f"Valid: {total_valid_rows}, "
            f"Attempts: {max_attempts}."
        )

    # -------------------------------------------------------------
    # Combine valid batches
    # -------------------------------------------------------------
    final_dataframe = (
        pd.concat(
            valid_batches,
            ignore_index=True,
        )
        .head(target_row_count)
    )

    # -------------------------------------------------------------
    # Final validation
    # -------------------------------------------------------------
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