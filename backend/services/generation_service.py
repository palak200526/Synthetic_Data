import logging

import pandas as pd

from backend.services.column_profile_service import build_column_profile
from backend.services.ollama_client import ensure_ollama_ready

logger = logging.getLogger(__name__)

from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
    save_generated_dataset,
)

from backend.services.business_rule_detector import (
    detect_arithmetic_relationships,
    apply_business_rules,
)

from backend.repositories.generation_repository import (
    create_generation_run,
    save_model_configuration,
    save_generated_result,
    update_generation_run_status,
)

from backend.repositories.validation_rules_repository import (
    get_validation_rules,
)

from backend.services.validation_resampling_service import (
    generate_valid_rows,
)

from backend.repositories.dataset_repository import (
    get_dataset_user_id,
)
from backend.generation.generator_factory import (
    get_generator
)

from backend.generation.llm_text import LLMTextGenerator

from backend.generation.llm_validator import (
    validate_rating_consistency,
    validate_sentiment_consistency,
)
from backend.utils.action_validator import validate_action

SUPPORTED_MODELS = {
    "gaussian_copula",
    "ctgan",
    "tvae",
    "llm_text",
    "llm",
}

# These belong to local LLM text generation, not CTGAN/TVAE/Copula.
_LLM_PARAMETER_KEYS = {
    "llm_text_batch_size",
    "llm_text_timeout",
    "llm_text_max_retries",
    "llm_text_similarity_threshold",
    "llm_model",
    "ollama_url",
}

_LLM_PARAMETER_MAP = {
    "llm_text_batch_size": "batch_size",
    "llm_text_timeout": "timeout",
    "llm_text_max_retries": "max_retries",
    "llm_text_similarity_threshold": "similarity_threshold",
    "llm_model": "model",
    "ollama_url": "ollama_url",
}


def _llm_generator_kwargs(parameters: dict | None) -> dict:
    kwargs = {}
    for source, dest in _LLM_PARAMETER_MAP.items():
        if parameters and source in parameters and parameters[source] is not None:
            kwargs[dest] = parameters[source]
    return kwargs


def _tabular_generator_parameters(parameters: dict | None) -> dict:
    return {
        key: value
        for key, value in (parameters or {}).items()
        if key not in _LLM_PARAMETER_KEYS
    }


# ==========================================================
# COLUMN ACTION HELPERS
# ==========================================================

def _get_columns_by_action(
    configurations: list,
    action: str,
) -> list[str]:
    """
    Return column names configured with a specific action.
    """
    target = validate_action(action)
    return [
        config["column_name"]
        for config in configurations
        if validate_action(config.get("action", "keep")) == target
    ]

def _get_llm_columns(
    configurations: list,
) -> list[str]:
    """
    Return column names configured to use LLM generation.
    """
    return [
        config["column_name"]
        for config in configurations
        if validate_action(config.get("action", "keep")) == "llm"
    ]


def _get_llm_configurations(
    configurations: list,
) -> list[dict]:
    """
    Return full configurations for columns configured to use LLM generation.
    """
    return [
        config
        for config in configurations
        if validate_action(config.get("action", "keep")) == "llm"
    ]

def _generate_unique_ids(
    result: pd.DataFrame,
    column_name: str,
) -> pd.DataFrame:
    """
    Generate new unique identifiers for a column.

    Requirements:
    - IDs must be unique.
    - IDs must not match any original/generated ID
      already present in the column.
    - Number of IDs must equal number of rows.
    """

    if column_name not in result.columns:
        return result

    # --------------------------------------------------
    # Preserve existing values before replacing them
    # --------------------------------------------------

    existing_values = set(
        result[column_name]
        .dropna()
        .astype(str)
        .tolist()
    )

    generated_ids = []

    index = 1

    while len(generated_ids) < len(result):

        new_id = (
            f"{column_name}_synthetic_{index:06d}"
        )

        if new_id not in existing_values:
            generated_ids.append(new_id)

        index += 1

    result[column_name] = generated_ids

    return result


# ==========================================================
# APPLY COLUMN ACTIONS
# ==========================================================

def _apply_column_actions(
    synthetic_dataframe: pd.DataFrame,
    configurations: list,
) -> pd.DataFrame:
    """
    Apply configured column actions after synthetic generation.

    Supported actions:
    - keep
    - remove
    - generalize
    - new_id
    - derived
    - llm
    """

    result = synthetic_dataframe.copy()

    # ==================================================
    # VALIDATE CONFIGURATIONS
    # ==================================================

    supported_actions = {
        "keep",
        "remove",
        "generalize",
        "new_id",
        "derived",
        "llm",
    }

    for config in configurations:
        raw_action = config.get("action")
        column_name = config.get("column_name")
        try:
            action = validate_action(raw_action)
            config["action"] = action
        except Exception:
            raise ValueError(
                f"Unsupported column action '{raw_action}' for column '{column_name}'"
            )

    # ==================================================
    # REMOVE
    # ==================================================

    remove_columns = _get_columns_by_action(
        configurations,
        "remove",
    )

    if remove_columns:

        result = result.drop(
            columns=remove_columns,
            errors="ignore",
        )


    # ==================================================
    # GENERALIZE
    # ==================================================

    generalize_columns = _get_columns_by_action(
        configurations,
        "generalize",
    )

    for column in generalize_columns:

        if column not in result.columns:
            continue

        # Numeric generalization
        if pd.api.types.is_numeric_dtype(
            result[column]
        ):

            result[column] = (
                result[column]
                .round(0)
            )

        # String/text generalization
        else:

            result[column] = (
                result[column]
                .astype(str)
                .str[:3]
            )

    # ==================================================
    # NEW ID
    # ==================================================

    new_id_columns = _get_columns_by_action(
        configurations,
        "new_id",
    )

    for column in new_id_columns:

        if column not in result.columns:
            continue

        result = _generate_unique_ids(
            result=result,
            column_name=column,
        )

    # ==================================================
    # DERIVED
    # ==================================================

    derived_configurations = [
        config
        for config in configurations
        if config["action"] == "derived"
    ]

    for config in derived_configurations:

        column_name = config["column_name"]

        rule = config.get("rule")

        if not rule:
            continue

        operation = rule.get(
            "operation"
        )

        operands = rule.get(
            "operands",
            [],
        )

        if len(operands) < 2:
            continue

        left = operands[0]
        right = operands[1]

        if (
            left not in result.columns
            or right not in result.columns
        ):
            continue

        # --------------------------------------------------
        # ADD
        # --------------------------------------------------

        if operation == "add":

            result[column_name] = (
                result[left]
                + result[right]
            )

        # --------------------------------------------------
        # SUBTRACT
        # --------------------------------------------------

        elif operation == "subtract":

            result[column_name] = (
                result[left]
                - result[right]
            )

        # --------------------------------------------------
        # MULTIPLY
        # --------------------------------------------------

        elif operation == "multiply":

            result[column_name] = (
                result[left]
                * result[right]
            )

        # --------------------------------------------------
        # DIVIDE
        # --------------------------------------------------

        elif operation == "divide":

            result[column_name] = 0.0

            non_zero = (
                result[right] != 0
            )

            result.loc[
                non_zero,
                column_name,
            ] = (
                result.loc[
                    non_zero,
                    left,
                ]
                /
                result.loc[
                    non_zero,
                    right,
                ]
            )

        else:

            raise ValueError(
                f"Unsupported derived "
                f"operation '{operation}' "
                f"for column '{column_name}'"
            )

    return result


# ==========================================================
# PREPARE DATAFRAME FOR GENERATION
# ==========================================================

def _prepare_generation_dataframe(
    dataframe: pd.DataFrame,
    configurations: list,
) -> pd.DataFrame:
    """
    Prepare dataframe before model training.

    Columns configured as 'remove' or 'llm' are excluded
    from the main synthetic-data model.
    """

    remove_columns = _get_columns_by_action(
        configurations,
        "remove",
    )

    llm_columns = _get_llm_columns(
        configurations,
    )

    columns_to_exclude = list(
        set(remove_columns + llm_columns)
    )

    generation_dataframe = (
        dataframe
        .drop(
            columns=columns_to_exclude,
            errors="ignore",
        )
        .copy()
    )

    if generation_dataframe.shape[1] == 0 and not llm_columns:
        raise ValueError(
            "No columns available for synthetic generation."
        )

    return generation_dataframe

# ==========================================================
# GENERATE USING SELECTED MODEL
# ==========================================================

def _generate_with_model(
    model_name: str,
    dataframe: pd.DataFrame,
    configurations: list,
    parameters: dict,
    num_rows: int,
) -> pd.DataFrame:
    """
    Train the selected generator and generate
    synthetic records.

    Identifier columns configured as new_id are
    passed to the generator so that generators
    can treat them separately.
    """

    # --------------------------------------------------
    # Prepare dataframe
    # --------------------------------------------------

    generation_dataframe = (
        _prepare_generation_dataframe(
            dataframe=dataframe,
            configurations=configurations,
        )
    )

    if generation_dataframe.shape[1] == 0:
        logger.info(
            "Skipping tabular generator; only LLM text columns remain."
        )
        return pd.DataFrame(index=range(num_rows))

    if model_name in {"llm", "llm_text", "text"}:
        logger.info(
            "LLM text model selected; generating structured columns with Gaussian Copula."
        )
        model_name = "gaussian_copula"

    # --------------------------------------------------
    # Get identifier columns
    # --------------------------------------------------

    identifier_columns = (
        _get_columns_by_action(
            configurations,
            "new_id",
        )
    )

    identifier_columns = [
        column
        for column in identifier_columns
        if column in generation_dataframe.columns
    ]

    # --------------------------------------------------
    # Generator parameters
    # --------------------------------------------------

    generator_parameters = _tabular_generator_parameters(parameters)

    # Identifier handling is controlled by
    # column configuration.
    generator_parameters.pop(
        "identifier_columns",
        None,
    )

    # --------------------------------------------------
    # Create generator
    # --------------------------------------------------

    generator = get_generator(
        model_name,
        **generator_parameters,
    )

    # --------------------------------------------------
    # Train
    # --------------------------------------------------

    generator.fit(
        generation_dataframe,
        identifier_columns=identifier_columns,
    )

    # --------------------------------------------------
    # Generate
    # --------------------------------------------------

    synthetic_dataframe = (
        generator.generate(
            num_rows=num_rows
        )
    )

    return synthetic_dataframe


def _get_rating_from_row(row: dict):
    """
    Extract a rating/score from a synthetic row.
    Returns None when no supported rating field is present.
    """

    rating_columns = [
        "rating",
        "score",
        "rating_score",
        "customer_rating",
        "review_rating",
    ]

    for column in rating_columns:
        if column not in row:
            continue

        value = row[column]

        try:
            rating = int(float(value))

            if 1 <= rating <= 5:
                return rating

        except (TypeError, ValueError):
            continue

    return None


_SAMPLE_LIMIT = 8
_SOURCE_EXACT_LIMIT = 2000
_CONTEXT_VALUE_MAX = 80
_CONTEXT_COLUMNS_MAX = 8


def _get_sentiment_from_row(row: dict) -> str | None:
    for key, value in row.items():
        if key.strip().lower() in ("sentiment", "tone", "sentiment_label"):
            if value is not None:
                try:
                    if not pd.isna(value):
                        return str(value).strip()
                except (TypeError, ValueError):
                    return str(value).strip()
    return None


def _validate_llm_value(
    value: str,
    row: dict,
    column_name: str,
    rule: dict,
) -> bool:
    """
    Validate an LLM-generated value using configured rules and structured row context.
    """
    if not value or not str(value).strip():
        return False

    # 1. Rating consistency
    rating = _get_rating_from_row(row)
    if rating is not None and isinstance(rule, dict) and rule.get("rating_consistency"):
        if not validate_rating_consistency(
            text=value,
            rating=rating,
            column_name=column_name,
        ):
            return False

    # 2. Sentiment consistency
    sentiment = _get_sentiment_from_row(row)
    if sentiment is not None:
        if not validate_sentiment_consistency(
            text=value,
            sentiment=sentiment,
        ):
            return False

    return True


def _sample_text_values(series: pd.Series, limit: int = _SAMPLE_LIMIT) -> list[str]:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return []
    count = min(limit, len(cleaned))
    return cleaned.sample(n=count, random_state=42).tolist()


def _source_guard_values(series: pd.Series) -> list[str]:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    unique = cleaned.drop_duplicates()
    if len(unique) > _SOURCE_EXACT_LIMIT:
        unique = unique.sample(n=_SOURCE_EXACT_LIMIT, random_state=42)
    return unique.tolist()


def _compact_row_context(row: dict, llm_column_names: set[str]) -> str:
    priority_keys = {"sentiment", "rating", "stars", "category", "status", "location", "source"}
    sorted_items = sorted(
        row.items(),
        key=lambda item: 0 if item[0].strip().lower() in priority_keys else 1,
    )
    parts = []
    for key, value in sorted_items:
        if key in llm_column_names:
            continue
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        text = str(value).strip()
        if not text:
            continue
        if len(text) > _CONTEXT_VALUE_MAX:
            text = text[: _CONTEXT_VALUE_MAX - 1] + "…"
        parts.append(f"{key}={text}")
        if len(parts) >= _CONTEXT_COLUMNS_MAX:
            break
    return ", ".join(parts)


def _needs_row_context(rule: dict, available_columns: list[str] | None = None) -> bool:
    if isinstance(rule, dict) and (rule.get("rating_consistency") or rule.get("use_row_context")):
        return True
    if available_columns:
        norm_cols = {c.strip().lower() for c in available_columns}
        if norm_cols & {"sentiment", "rating", "category", "status", "stars", "feedback_type"}:
            return True
    return False


def _generate_llm_columns(
    original_dataframe: pd.DataFrame,
    synthetic_dataframe: pd.DataFrame,
    configurations: list,
    progress_callback=None,
    llm_kwargs: dict | None = None,
) -> pd.DataFrame:
    """
    Generate synthetic values for columns configured
    with the 'llm' action using the local Ollama model.
    """
    llm_configurations = _get_llm_configurations(configurations)

    if not llm_configurations:
        return synthetic_dataframe

    kwargs = dict(llm_kwargs or {})
    health_base = kwargs.get("ollama_url")
    if health_base:
        health_base = str(health_base).replace("/api/generate", "").rstrip("/")
    ensure_ollama_ready(
        model=kwargs.get("model"),
        base_url=health_base,
    )
    kwargs["skip_health_check"] = True

    result = synthetic_dataframe.copy()
    llm_names = {
        config.get("column_name")
        for config in llm_configurations
        if config.get("column_name")
    }
    llm_generator = LLMTextGenerator(**kwargs)
    total_columns = len(llm_configurations)

    for column_index, config in enumerate(llm_configurations, start=1):
        column_name = config.get("column_name")
        if not column_name or column_name not in original_dataframe.columns:
            logger.warning(
                "Skipping LLM column %s; not present in source dataset",
                column_name,
            )
            continue

        llm_rule = config.get("rule") or {}
        if not isinstance(llm_rule, dict):
            llm_rule = {}

        series = original_dataframe[column_name]
        sample_values = _sample_text_values(series)
        source_values = _source_guard_values(series)
        profile = build_column_profile(original_dataframe, column_name)

        extra_context = ""
        if llm_rule:
            extra_context = (
                "Column-specific rules (do not copy source text):\n"
                f"{llm_rule}"
            )

        row_count = len(result)
        logger.info(
            "LLM column generation column=%s rows=%s samples=%s",
            column_name,
            row_count,
            len(sample_values),
        )

        def _column_progress(meta: dict) -> None:
            if not progress_callback:
                return
            payload = dict(meta)
            payload["llm_column_index"] = column_index
            payload["llm_column_total"] = total_columns
            progress_callback(payload)

        use_row_context = _needs_row_context(llm_rule, list(result.columns))
        row_records = (
            result.to_dict(orient="records") if use_row_context else []
        )
        row_contexts = [
            _compact_row_context(row, llm_names) for row in row_records
        ] if use_row_context else None

        generated_values = llm_generator.generate(
            column_name=column_name,
            count=row_count,
            sample_values=sample_values,
            profile=profile,
            extra_context=extra_context,
            row_contexts=row_contexts,
            source_values=source_values,
            progress_callback=_column_progress,
        )

        has_structured_context = any(
            c.strip().lower() in ("sentiment", "rating", "stars")
            for c in result.columns
        )
        if llm_rule.get("rating_consistency") or llm_rule.get("sentiment_consistency") or has_structured_context:
            generated_values = _retry_invalid_llm_rows(
                llm_generator=llm_generator,
                column_name=column_name,
                generated_values=generated_values,
                row_records=row_records or result.to_dict(orient="records"),
                llm_rule=llm_rule,
                sample_values=sample_values,
                profile=profile,
                extra_context=extra_context,
                source_values=source_values,
                llm_names=llm_names,
            )

        result[column_name] = generated_values

    return result


def _retry_invalid_llm_rows(
    *,
    llm_generator: LLMTextGenerator,
    column_name: str,
    generated_values: list[str],
    row_records: list[dict],
    llm_rule: dict,
    sample_values: list[str],
    profile: dict,
    extra_context: str,
    source_values: list[str],
    llm_names: set[str],
) -> list[str]:
    final_values = list(generated_values)
    pending = [
        index
        for index, value in enumerate(final_values)
        if not _validate_llm_value(
            value=value,
            row=row_records[index],
            column_name=column_name,
            rule=llm_rule,
        )
    ]

    attempt = 0
    max_retries = llm_generator.max_retries
    while pending and attempt < max_retries:
        attempt += 1
        logger.info(
            "LLM rating-consistency retry column=%s pending=%s attempt=%s",
            column_name,
            len(pending),
            attempt,
        )
        contexts = [
            _compact_row_context(row_records[index], llm_names)
            for index in pending
        ]
        replacements = llm_generator.generate(
            column_name=column_name,
            count=len(pending),
            sample_values=sample_values,
            profile=profile,
            extra_context=(
                extra_context
                + "\nRegenerate values that match the row rating/style. "
                "Do not copy previous invalid text."
            ),
            row_contexts=contexts,
            source_values=source_values,
        )
        still_pending = []
        for offset, index in enumerate(pending):
            candidate = replacements[offset]
            if _validate_llm_value(
                value=candidate,
                row=row_records[index],
                column_name=column_name,
                rule=llm_rule,
            ):
                final_values[index] = candidate
            else:
                still_pending.append(index)
        pending = still_pending

    if pending:
        if llm_rule.get("strict_consistency"):
            raise ValueError(
                f"Could not generate valid LLM values for {len(pending)} rows "
                f"in column '{column_name}' after {max_retries} attempts."
            )
        logger.warning(
            "Could not fully satisfy LLM consistency for %d rows in column '%s' "
            "after %d attempts; retaining best-effort generated text.",
            len(pending),
            column_name,
            max_retries,
        )
    return final_values


def generate_rows(
    original_dataframe: pd.DataFrame,
    configurations: list,
    model_name: str,
    num_rows: int,
    parameters: dict | None = None,
    progress_callback=None,
    business_rules: list | None = None,
) -> pd.DataFrame:
    """
    Train the selected tabular generator, fill LLM text columns,
    then apply column actions. Used by the main service and tests.
    """
    generated = _generate_with_model(
        model_name=model_name,
        dataframe=original_dataframe,
        configurations=configurations,
        parameters=parameters or {},
        num_rows=num_rows,
    )

    if progress_callback:
        progress_callback(
            {
                "stage": "tabular",
                "percent": 40,
            }
        )

    if business_rules:
        generated = apply_business_rules(
            generated,
            business_rules,
        )

    generated = _generate_llm_columns(
        original_dataframe=original_dataframe,
        synthetic_dataframe=generated,
        configurations=configurations,
        progress_callback=progress_callback,
        llm_kwargs=_llm_generator_kwargs(parameters),
    )

    generated = _apply_column_actions(
        synthetic_dataframe=generated,
        configurations=configurations,
    )
    return generated

# ==========================================================
# MAIN GENERATION SERVICE
# ==========================================================

def generate_synthetic_dataset(
    dataset_id,
    model_name,
    user_id,
    parameters: dict | None = None,
    progress_callback=None,
):
    """
    Main synthetic data generation service.

    Flow:

    1. Validate dataset ownership
    2. Validate generation model
    3. Create generation run
    4. Load dataset and configurations
    5. Load validation rules
    6. Detect business rules
    7. Train selected generator
    8. Generate synthetic data
    9. Apply business rules
    10. Apply configured column actions
    11. Validate/resample
    12. Save generated dataset
    13. Save generation result
    14. Update generation run
    15. Return API response
    """

    # ==================================================
    # 1. DATASET OWNERSHIP
    # ==================================================

    dataset_user_id = get_dataset_user_id(
        dataset_id
    )

    if dataset_user_id != user_id:

        raise PermissionError(
            "You do not have permission to "
            "generate data for this dataset."
        )

    # ==================================================
    # 2. VALIDATE MODEL
    # ==================================================

    if not model_name:

        raise ValueError(
            "Model name is required."
        )

    model_name = (
        model_name
        .strip()
        .lower()
    )

    if model_name not in SUPPORTED_MODELS:

        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models: "
            f"{', '.join(sorted(SUPPORTED_MODELS))}."
        )

    parameters = parameters or {}

    # ==================================================
    # 3. CREATE GENERATION RUN
    # ==================================================

    run_id = create_generation_run(
        dataset_id=dataset_id,
        model_name=model_name,
    )

    save_model_configuration(
        run_id=run_id,
        model_name=model_name,
        parameters=parameters,
    )

    try:
        return _run_generation_pipeline(
            dataset_id=dataset_id,
            model_name=model_name,
            parameters=parameters,
            run_id=run_id,
            progress_callback=progress_callback,
        )
    except Exception:
        logger.exception("Generation run %s failed", run_id)
        try:
            update_generation_run_status(
                run_id=run_id,
                status="failed",
            )
        except Exception:
            logger.exception(
                "Could not mark generation run %s as failed",
                run_id,
            )
        raise


def _run_generation_pipeline(
    *,
    dataset_id,
    model_name,
    parameters,
    run_id,
    progress_callback=None,
):
    # ==================================================
    # 4. PREPARE DATASET
    # ==================================================

    preparation = (
        prepare_dataset_for_generation(
            dataset_id
        )
    )

    dataframe = preparation[
        "dataframe"
    ]

    filename = preparation[
        "filename"
    ]

    configurations = preparation[
        "configurations"
    ]

    # ==================================================
    # 5. VALIDATION RULES
    # ==================================================

    validation_rules = (
        get_validation_rules(
            dataset_id
        )
    )

    # ==================================================
    # 6. DETECT BUSINESS RULES
    # ==================================================

    print(f"[generation] Detecting business rules on {len(dataframe.columns)} columns...")
    business_rules = detect_arithmetic_relationships(dataframe)
    print(f"[generation] Found {len(business_rules)} business rules.")

    def generate_batch(count):
        return generate_rows(
            original_dataframe=dataframe,
            configurations=configurations,
            model_name=model_name,
            num_rows=count,
            parameters=parameters,
            progress_callback=progress_callback,
            business_rules=business_rules,
        )

    # ==================================================
    # 8. GENERATE + VALIDATE
    # ==================================================

    if validation_rules:

        validation_result = (
            generate_valid_rows(
                generate_function=generate_batch,
                target_row_count=len(dataframe),
                rules=validation_rules,
                max_attempts=10,
            )
        )

        synthetic_dataframe = (
            validation_result["dataframe"]
        )

    else:

        synthetic_dataframe = generate_batch(
            len(dataframe)
        )

        validation_result = {

            "dataframe":
                synthetic_dataframe,

            "target_row_count":
                len(dataframe),

            "total_generated_rows":
                len(synthetic_dataframe),

            "total_valid_rows":
                len(synthetic_dataframe),

            "total_rejected_rows":
                0,

            "attempts":
                1,

            "validation_history":
                [],

            "final_validation": {

                "valid":
                    True,

                "valid_row_count":
                    len(synthetic_dataframe),

                "invalid_row_count":
                    0,

                "invalid_rows":
                    [],

                "rules":
                    [],
            },
        }

    # ==================================================
    # 9. SAVE GENERATED DATASET
    # ==================================================

    generated_dataset = (
        save_generated_dataset(
            synthetic_dataframe,
            dataset_id,
            model_name,
        )
    )

    # ==================================================
    # 10. SAVE GENERATION RESULT
    # ==================================================

    result_id = save_generated_result(
        run_id=run_id,

        file_name=generated_dataset[
            "file_name"
        ],

        file_path=generated_dataset[
            "file_path"
        ],

        row_count=generated_dataset[
            "row_count"
        ],

        column_count=generated_dataset[
            "column_count"
        ],
    )

    # ==================================================
    # 11. UPDATE GENERATION RUN STATUS
    # ==================================================

    update_generation_run_status(
        run_id=run_id,
        status="completed",
    )

    # ==================================================
    # 12. API RESPONSE
    # ==================================================

    return {

        "status":
            "success",

        "message":
            "Synthetic dataset generated successfully.",

        "data": {

            "run_id":
                run_id,

            "result_id":
                result_id,

            "dataset_id":
                dataset_id,

            "model_name":
                model_name,

            "parameters":
                parameters,

            "source_filename":
                filename,

            "configurations":
                configurations,

            "generated_dataset":
                generated_dataset,

            "business_rules":
                business_rules,

            "validation": {

                "target_row_count":
                    validation_result[
                        "target_row_count"
                    ],

                "total_generated_rows":
                    validation_result[
                        "total_generated_rows"
                    ],

                "total_valid_rows":
                    validation_result[
                        "total_valid_rows"
                    ],

                "total_rejected_rows":
                    validation_result[
                        "total_rejected_rows"
                    ],

                "attempts":
                    validation_result[
                        "attempts"
                    ],

                "final_validation":
                    validation_result[
                        "final_validation"
                    ],
            },
        },
    }