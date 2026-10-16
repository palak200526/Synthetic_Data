import asyncio
import inspect
import logging
import os

import pandas as pd

from backend.services.column_profile_service import build_column_profile
from backend.services.id_pattern_service import generate_ids_like
from backend.services.progress_service import ProgressReporter
from backend.services.ollama_client import ensure_ollama_ready

logger = logging.getLogger(__name__)

from backend.services.generated_dataset_service import (
    prepare_dataset_for_generation,
    save_generated_dataset,
)
from backend.services.missing_value_service import handle_missing_values

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

from backend.generation.llm_text import LLMTextGenerator, run_coroutine_sync

from backend.generation.llm_validator import (
    validate_rating_consistency,
    validate_sentiment_consistency,
)
from backend.repositories.generation_job_repository import (
    create_generation_job,
    get_generation_job,
    update_generation_job_progress,
    update_generation_job_status,
)
from backend.services.generation_checkpoint_service import (
    check_job_control,
    clear_job_control,
    clear_local_job_control,
    delete_checkpoint,
    load_checkpoint_rows,
    pop_auto_pause_reason,
    save_checkpoint_rows,
)
from backend.utils.action_validator import validate_action


def _compute_checkpoint_batch_size(target_row_count: int, param_batch: int | None = None) -> int:
    if param_batch and int(param_batch) > 0:
        return min(int(param_batch), target_row_count)
    if target_row_count <= 20:
        return max(5, target_row_count // 2 or 1)
    if target_row_count <= 100:
        return 25
    if target_row_count <= 500:
        return 100
    return 200

from backend.services.quality_enhancement_service import (
    detect_derived_features,
    apply_derived_features,
    apply_rank_preserving_marginal_matching,
    match_categorical_frequencies,
    compute_correlation_error,
    privacy_guard_filter,
    encode_cyclical_datetimes,
    decode_cyclical_datetimes,
)

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
    "llm_text_max_concurrency",
    "llm_text_timeout",
    "llm_text_max_retries",
    "llm_text_similarity_threshold",
    "llm_model",
    "ollama_url",
}

_QUALITY_PARAMETER_KEYS = {
    "enable_quality_enhancements",
    "enable_derived_features",
    "enable_cyclical_encoding",
    "enable_type_optimization",
    "enable_subgroup_conditioning",
    "enable_marginal_matching",
    "enable_categorical_matching",
    "enable_privacy_guard",
    "enable_correlation_repair",
    "overgenerate_factor",
    "best_of_n",
    "max_exact_duplicate_rate",
}

_LLM_PARAMETER_MAP = {
    "llm_text_batch_size": "batch_size",
    "llm_text_max_concurrency": "max_concurrency",
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
        if key not in _LLM_PARAMETER_KEYS and key not in _QUALITY_PARAMETER_KEYS
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
    original_dataframe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Generate new unique identifiers for a column.

    The new IDs copy the format of the original IDs (same prefix, length,
    letter case, numeric type ...), so e.g. CUST-0042 becomes CUST-0731
    rather than customer_id_synthetic_000001.

    Requirements:
    - IDs must be unique.
    - IDs must not match any original/generated ID
      already present in the column.
    - Number of IDs must equal number of rows.
    """

    if column_name not in result.columns:
        return result

    # --------------------------------------------------
    # Learn the format from the ORIGINAL column; fall back
    # to whatever the generator produced if it is missing.
    # --------------------------------------------------

    if (
        original_dataframe is not None
        and column_name in original_dataframe.columns
    ):
        source = original_dataframe[column_name]
    else:
        source = result[column_name]

    existing_values = result[column_name].dropna().tolist()

    result[column_name] = generate_ids_like(
        source=source,
        count=len(result),
        existing=existing_values,
    )

    return result


# ==========================================================
# APPLY COLUMN ACTIONS
# ==========================================================

def _apply_column_actions(
    synthetic_dataframe: pd.DataFrame,
    configurations: list,
    original_dataframe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Apply configured column actions after synthetic generation.

    Supported actions:
    - keep
    - remove
    - new_id
    - llm
    """

    result = synthetic_dataframe.copy()

    # ==================================================
    # VALIDATE CONFIGURATIONS
    # ==================================================

    supported_actions = {
        "keep",
        "remove",
        "new_id",
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
            original_dataframe=original_dataframe,
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

def _fit_model(
    model_name: str,
    dataframe: pd.DataFrame,
    configurations: list,
    parameters: dict,
    reporter: ProgressReporter | None = None,
):
    """
    Prepare data and fit the selected generator.
    Returns the fitted generator instance.
    """
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
        return None

    if model_name in {"llm", "llm_text", "text"}:
        logger.info(
            "LLM text model selected; generating structured columns with Gaussian Copula."
        )
        model_name = "gaussian_copula"

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

    generator_parameters = _tabular_generator_parameters(parameters)
    generator_parameters.pop(
        "identifier_columns",
        None,
    )

    generator = get_generator(
        model_name,
        **generator_parameters,
    )

    fit_kwargs = {"identifier_columns": identifier_columns}

    if reporter:
        reporter.start("train")

        def _epoch_progress(epoch: int, epochs: int) -> None:
            reporter.update(
                "train",
                epoch / max(epochs, 1),
                message=f"Epoch {epoch} of {epochs}",
                epoch=epoch,
                epochs=epochs,
            )

        if "progress_callback" in inspect.signature(
            generator.fit
        ).parameters:
            fit_kwargs["progress_callback"] = _epoch_progress

    generator.fit(
        generation_dataframe,
        **fit_kwargs,
    )

    if reporter:
        reporter.complete("train")

    return generator


def _generate_with_model(
    model_name: str,
    dataframe: pd.DataFrame,
    configurations: list,
    parameters: dict,
    num_rows: int,
    reporter: ProgressReporter | None = None,
    fitted_generator=None,
) -> pd.DataFrame:
    """
    Train the selected generator (or reuse an already fitted generator)
    and sample synthetic records.
    """
    generator = fitted_generator
    if generator is None:
        generator = _fit_model(
            model_name=model_name,
            dataframe=dataframe,
            configurations=configurations,
            parameters=parameters,
            reporter=reporter,
        )

    if generator is None:
        return pd.DataFrame(index=range(num_rows))

    if reporter:
        reporter.start(
            "sample",
            message=f"Sampling {num_rows:,} rows",
        )

    synthetic_dataframe = (
        generator.generate(
            num_rows=num_rows
        )
    )

    if reporter:
        reporter.complete("sample")

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

    # ------------------------------------------------------------------
    # Phase 1: prepare every column (cheap, CPU only).
    # LLM columns are excluded from each other's row context
    # (_compact_row_context drops llm_names), so they are independent and
    # can be generated at the same time.
    # ------------------------------------------------------------------
    jobs: list[dict] = []
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

        use_row_context = _needs_row_context(llm_rule, list(result.columns))
        row_records = (
            result.to_dict(orient="records") if use_row_context else []
        )
        row_contexts = [
            _compact_row_context(row, llm_names) for row in row_records
        ] if use_row_context else None

        logger.info(
            "LLM column generation column=%s rows=%s samples=%s",
            column_name,
            len(result),
            len(sample_values),
        )

        jobs.append(
            {
                "column_index": column_index,
                "column_name": column_name,
                "llm_rule": llm_rule,
                "sample_values": sample_values,
                "source_values": source_values,
                "profile": profile,
                "extra_context": extra_context,
                "row_records": row_records,
                "row_contexts": row_contexts,
            }
        )

    if not jobs:
        return result

    # ------------------------------------------------------------------
    # Phase 2: generate all columns concurrently on ONE event loop.
    # A single semaphore bounds the total number of in-flight Ollama
    # requests, so more columns never means more load than
    # max_concurrency allows.
    # ------------------------------------------------------------------
    row_count = len(result)
    progress_state = {job["column_name"]: 0 for job in jobs}
    total_requested = row_count * len(jobs)

    def _make_progress(job: dict):
        def _column_progress(meta: dict) -> None:
            if not progress_callback:
                return
            progress_state[job["column_name"]] = int(meta.get("generated") or 0)
            if len(jobs) == 1:
                payload = dict(meta)
                payload["llm_column_index"] = job["column_index"]
                payload["llm_column_total"] = total_columns
            else:
                payload = {
                    "stage": "llm_text",
                    "column": ", ".join(progress_state),
                    "batch": meta.get("batch"),
                    "generated": sum(progress_state.values()),
                    "requested": total_requested,
                    "llm_column_index": 1,
                    "llm_column_total": 1,
                }
            progress_callback(payload)

        return _column_progress

    parallel_columns = (
        os.getenv("LLM_TEXT_PARALLEL_COLUMNS", "1").strip().lower()
        not in {"0", "false", "no"}
    )

    async def _run_all() -> list[list[str]]:
        shared_semaphore = asyncio.Semaphore(llm_generator.max_concurrency)

        async def _one(job: dict) -> list[str]:
            return await llm_generator.async_generate(
                column_name=job["column_name"],
                count=row_count,
                sample_values=job["sample_values"],
                profile=job["profile"],
                extra_context=job["extra_context"],
                row_contexts=job["row_contexts"],
                source_values=job["source_values"],
                progress_callback=_make_progress(job),
                semaphore=shared_semaphore,
            )

        if parallel_columns:
            return list(await asyncio.gather(*[_one(job) for job in jobs]))

        outputs = []
        for job in jobs:
            outputs.append(await _one(job))
        return outputs

    all_values = run_coroutine_sync(_run_all())

    # ------------------------------------------------------------------
    # Phase 3: consistency retries + assignment
    # ------------------------------------------------------------------
    for job, generated_values in zip(jobs, all_values):
        column_name = job["column_name"]
        llm_rule = job["llm_rule"]

        has_structured_context = any(
            c.strip().lower() in ("sentiment", "rating", "stars")
            for c in result.columns
        )
        if (
            llm_rule.get("rating_consistency")
            or llm_rule.get("sentiment_consistency")
            or has_structured_context
        ):
            generated_values = _retry_invalid_llm_rows(
                llm_generator=llm_generator,
                column_name=column_name,
                generated_values=generated_values,
                row_records=job["row_records"] or result.to_dict(orient="records"),
                llm_rule=llm_rule,
                sample_values=job["sample_values"],
                profile=job["profile"],
                extra_context=job["extra_context"],
                source_values=job["source_values"],
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
    reporter: ProgressReporter | None = None,
    fitted_generator=None,
    apply_post_enhancements: bool = True,
) -> pd.DataFrame:
    """
    Train or sample the selected tabular generator, fill LLM text columns,
    then apply column actions and quality enhancements.
    """
    params = dict(parameters or {})

    # Best-of-N candidate selection (Step 3d)
    best_of_n = int(params.get("best_of_n", 1))
    # Best-of-N would re-run the (slow) LLM text generation N times, so it is
    # skipped whenever LLM columns are configured.
    if best_of_n > 1 and fitted_generator is None and not _get_llm_configurations(configurations):
        best_df = None
        best_score = -1e9
        base_seed = int(params.get("random_state", 42))
        for cand_idx in range(best_of_n):
            cand_params = dict(params)
            cand_params["best_of_n"] = 1  # prevent recursion
            cand_params["random_state"] = base_seed + cand_idx * 17
            cand_df = generate_rows(
                original_dataframe=original_dataframe,
                configurations=configurations,
                model_name=model_name,
                num_rows=num_rows,
                parameters=cand_params,
                progress_callback=progress_callback,
                business_rules=business_rules,
                reporter=reporter,
                fitted_generator=fitted_generator,
                apply_post_enhancements=apply_post_enhancements,
            )
            corr_err = compute_correlation_error(original_dataframe, cand_df)
            score = 100.0 * (1.0 - corr_err)
            if score > best_score or best_df is None:
                best_score = score
                best_df = cand_df
        return best_df if best_df is not None else original_dataframe.head(num_rows)

    has_llm = bool(_get_llm_configurations(configurations))
    if reporter is None:
        reporter = ProgressReporter(progress_callback, model_name=model_name)
        reporter.configure(
            has_llm=has_llm,
        )

    enable_enhancements = params.get("enable_quality_enhancements", True)
    enable_derived = params.get("enable_derived_features", True) if enable_enhancements else False
    enable_marginal = params.get("enable_marginal_matching", True) if enable_enhancements else False
    enable_categorical = params.get("enable_categorical_matching", True) if enable_enhancements else False
    enable_privacy = params.get("enable_privacy_guard", True) if enable_enhancements else False
    overgen_factor = float(params.get("overgenerate_factor", 1.25)) if (enable_enhancements and not has_llm and apply_post_enhancements) else 1.0

    # Step 1: Detect derived features (arithmetic, date diffs)
    derived_rules = []
    train_df = original_dataframe
    if enable_derived:
        try:
            derived_rules = detect_derived_features(original_dataframe)
            derived_targets = [r["target"] for r in derived_rules if r.get("target")]
            if derived_targets:
                train_df = original_dataframe.drop(columns=derived_targets, errors="ignore")
        except Exception as exc:
            logger.warning("Could not process derived features: %s", exc)

    gen_rows_count = int(num_rows * overgen_factor) if overgen_factor > 1.0 else num_rows

    generated = _generate_with_model(
        model_name=model_name,
        dataframe=train_df,
        configurations=configurations,
        parameters=parameters or {},
        num_rows=gen_rows_count,
        reporter=reporter,
        fitted_generator=fitted_generator,
    )

    # Step 1 & 3: Recompute derived features
    if derived_rules:
        generated = apply_derived_features(generated, derived_rules)

    if business_rules:
        generated = apply_business_rules(
            generated,
            business_rules,
        )

    def _llm_progress(meta: dict) -> None:
        total = meta.get("llm_column_total") or 1
        index = meta.get("llm_column_index") or 1
        requested = meta.get("requested") or 0
        done = meta.get("generated") or 0
        inner = min(done / requested, 1.0) if requested else 0.0
        reporter.update(
            "llm_text",
            ((index - 1) + inner) / total,
            message=(
                f"Column '{meta.get('column')}' "
                f"({done}/{requested or '?'})"
            ),
            column=meta.get("column"),
            batch=meta.get("batch"),
            generated=done,
            requested=requested,
            llm_column_index=index,
            llm_column_total=total,
        )

    reporter.start("llm_text")
    generated = _generate_llm_columns(
        original_dataframe=original_dataframe,
        synthetic_dataframe=generated,
        configurations=configurations,
        progress_callback=_llm_progress,
        llm_kwargs=_llm_generator_kwargs(parameters),
    )
    reporter.complete("llm_text")

    generated = _apply_column_actions(
        synthetic_dataframe=generated,
        configurations=configurations,
        original_dataframe=original_dataframe,
    )

    # Step 3 & 5: Post-generation marginal matching, categorical matching, privacy guard
    if apply_post_enhancements and enable_enhancements:
        if enable_marginal:
            generated = apply_rank_preserving_marginal_matching(original_dataframe, generated)
        if enable_categorical:
            generated = match_categorical_frequencies(original_dataframe, generated)
        if enable_privacy:
            generated, _ = privacy_guard_filter(
                real_df=original_dataframe,
                synthetic_df=generated,
                max_exact_duplicate_rate=float(params.get("max_exact_duplicate_rate", 0.01)),
            )

    if len(generated) > num_rows:
        generated = generated.head(num_rows).reset_index(drop=True)

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
    job_id: str | None = None,
    resume: bool = False,
):
    """
    Main synthetic data generation service with persistent checkpoint and resume support.
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

    if job_id and resume:
        db_job = get_generation_job(job_id)
        if db_job:
            if not parameters and db_job.get("parameters"):
                parameters = db_job["parameters"]
            if not model_name and db_job.get("model_name"):
                model_name = db_job["model_name"]
    elif job_id and not resume:
        # Memory-only: a pause the user clicked while the job was still queued
        # lives in the DB and must survive the start-up of a fresh job.
        clear_local_job_control(job_id)
        delete_checkpoint(job_id)

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
            job_id=job_id,
            resume=resume,
        )
    except Exception as exc:
        logger.exception("Generation run %s failed", run_id)
        if job_id:
            try:
                update_generation_job_status(
                    job_id=job_id,
                    status="failed",
                    error_message=str(exc),
                )
            except Exception:
                pass
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
    job_id: str | None = None,
    resume: bool = False,
):
    # ==================================================
    # 4. PREPARE DATASET
    # ==================================================

    reporter = ProgressReporter(
        progress_callback,
        model_name=model_name,
    )
    reporter.start("prepare", message="Loading dataset and column settings")

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

    target_row_count = int(parameters.get("num_rows", len(dataframe))) if parameters and parameters.get("num_rows") else len(dataframe)
    batch_size = _compute_checkpoint_batch_size(target_row_count, parameters.get("checkpoint_batch_size"))
    total_batches = max(1, (target_row_count + batch_size - 1) // batch_size)

    if job_id:
        existing_job = get_generation_job(job_id)
        if not existing_job:
            try:
                create_generation_job(
                    job_id=job_id,
                    user_id=get_dataset_user_id(dataset_id),
                    dataset_id=dataset_id,
                    file_name=filename,
                    model_name=model_name,
                    total_rows=target_row_count,
                    parameters=parameters,
                    column_configurations=configurations,
                    llm_model=(parameters or {}).get("llm_model"),
                )
            except Exception as exc:
                logger.debug("Job %s might already exist: %s", job_id, exc)

    # ==================================================
    # 5. VALIDATION RULES
    # ==================================================

    validation_rules = (
        get_validation_rules(
            dataset_id
        )
    )

    reporter.configure(
        has_llm=bool(_get_llm_configurations(configurations)),
        has_validation=bool(validation_rules),
    )
    reporter.complete("prepare")

    # ==================================================
    # 6. DETECT BUSINESS RULES
    # ==================================================

    reporter.start(
        "rules",
        message=f"Scanning {len(dataframe.columns)} columns",
    )
    business_rules = detect_arithmetic_relationships(dataframe)
    reporter.complete("rules")

    # ==================================================
    # 7. CHECKPOINT & RESUME INITIALIZATION
    # ==================================================

    accumulated_rows: list[pd.DataFrame] = []
    already_generated_count = 0
    current_batch_num = 0

    if job_id and resume:
        checkpoint_df = load_checkpoint_rows(job_id)
        if checkpoint_df is not None and not checkpoint_df.empty:
            accumulated_rows.append(checkpoint_df)
            already_generated_count = len(checkpoint_df)
            current_batch_num = (already_generated_count + batch_size - 1) // batch_size
            logger.info(
                "Resuming job %s: loaded %d rows from checkpoint",
                job_id,
                already_generated_count,
            )
            update_generation_job_status(
                job_id=job_id,
                status="running",
                stage_message=f"Resumed {already_generated_count}/{target_row_count} rows from checkpoint",
            )
            # NOTE: do not report the "sample" floor here. The model still has
            # to be re-trained before sampling continues, and the overall
            # progress bar never goes backwards - reporting "sample" now made
            # it jump to ~67% (training counted as done) and sit there while
            # the model was actually retraining. The sample floor is reported
            # from the batch loop once training is finished.
    elif job_id and not resume:
        delete_checkpoint(job_id)
        update_generation_job_status(
            job_id=job_id,
            status="running",
            stage_message="Starting generation",
        )

    # ==================================================
    # 8. TRAIN GENERATOR & BATCH GENERATION LOOP
    # ==================================================

    params = dict(parameters or {})
    enable_enhancements = params.get("enable_quality_enhancements", True)
    enable_derived = params.get("enable_derived_features", True) if enable_enhancements else False

    derived_rules = []
    train_df = dataframe
    if enable_derived:
        try:
            derived_rules = detect_derived_features(dataframe)
            derived_targets = [r["target"] for r in derived_rules if r.get("target")]
            if derived_targets:
                train_df = dataframe.drop(columns=derived_targets, errors="ignore")
        except Exception as exc:
            logger.warning("Could not process derived features: %s", exc)

    fitted_generator = None
    if already_generated_count < target_row_count:
        fitted_generator = _fit_model(
            model_name=model_name,
            dataframe=train_df,
            configurations=configurations,
            parameters=parameters or {},
            reporter=reporter,
        )

    while already_generated_count < target_row_count:
        if job_id:
            ctrl = check_job_control(job_id)
            if ctrl == "pause":
                clear_job_control(job_id)
                update_generation_job_status(
                    job_id=job_id,
                    status="paused",
                    stage_message=f"Paused by user at {already_generated_count}/{target_row_count} rows",
                )
                return {
                    "status": "paused",
                    "job_id": job_id,
                    "generated_rows": already_generated_count,
                    "target_rows": target_row_count,
                }
            elif ctrl == "cancel":
                clear_job_control(job_id)
                delete_checkpoint(job_id)
                update_generation_job_status(
                    job_id=job_id,
                    status="cancelled",
                    stage_message="Cancelled by user",
                )
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                }

        batch_target = min(batch_size, target_row_count - already_generated_count)
        current_batch_num += 1

        reporter.start(
            "sample",
            message=f"Generating batch {current_batch_num} of {total_batches} ({already_generated_count}/{target_row_count} rows)",
        )

        batch_df = generate_rows(
            original_dataframe=dataframe,
            configurations=configurations,
            model_name=model_name,
            num_rows=batch_target,
            parameters=parameters,
            business_rules=business_rules,
            reporter=reporter,
            fitted_generator=fitted_generator,
            apply_post_enhancements=False,
        )

        if validation_rules:
            from backend.services.validation_engine import validate_dataframe
            val_res = validate_dataframe(batch_df, validation_rules)
            invalid_indices = set(val_res.get("invalid_rows", []))
            if invalid_indices:
                batch_df = batch_df.drop(index=list(invalid_indices), errors="ignore").reset_index(drop=True)

        if len(batch_df) > 0:
            accumulated_rows.append(batch_df)
            already_generated_count = sum(len(b) for b in accumulated_rows)

        # Durable checkpoint after every batch
        if job_id and accumulated_rows:
            current_combined = pd.concat(accumulated_rows, ignore_index=True)
            checkpoint_file = save_checkpoint_rows(job_id, current_combined)
            progress_pct = int(min(100, (already_generated_count / max(1, target_row_count)) * 100))
            update_generation_job_progress(
                job_id=job_id,
                generated_rows=min(already_generated_count, target_row_count),
                current_batch=current_batch_num,
                total_batches=total_batches,
                progress_percent=progress_pct,
                stage="sample",
                stage_message=f"Batch {current_batch_num}/{total_batches} completed ({min(already_generated_count, target_row_count)}/{target_row_count} rows)",
                checkpoint_path=checkpoint_file,
            )

        if job_id:
            # Checked right after a batch is safely checkpointed: if the
            # browser is gone (tab closed / signed out / token expired) the
            # run pauses itself here instead of running unattended.
            ctrl = check_job_control(job_id, idle_pause=True)
            if ctrl == "pause":
                clear_job_control(job_id)
                saved_rows = min(already_generated_count, target_row_count)
                if pop_auto_pause_reason(job_id) == "idle":
                    pause_message = (
                        f"Paused automatically at {saved_rows}/{target_row_count} rows "
                        "(browser closed or signed out). Progress is saved - resume to continue."
                    )
                else:
                    pause_message = f"Paused by user at {saved_rows}/{target_row_count} rows"
                update_generation_job_status(
                    job_id=job_id,
                    status="paused",
                    stage_message=pause_message,
                )
                return {
                    "status": "paused",
                    "job_id": job_id,
                    "generated_rows": min(already_generated_count, target_row_count),
                    "target_rows": target_row_count,
                }
            elif ctrl == "cancel":
                clear_job_control(job_id)
                delete_checkpoint(job_id)
                update_generation_job_status(
                    job_id=job_id,
                    status="cancelled",
                    stage_message="Cancelled by user",
                )
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                }

    synthetic_dataframe = (
        pd.concat(accumulated_rows, ignore_index=True)
        if accumulated_rows
        else pd.DataFrame()
    )

    if len(synthetic_dataframe) > target_row_count:
        synthetic_dataframe = synthetic_dataframe.head(target_row_count).reset_index(drop=True)

    # Post-generation enhancements on the combined dataset
    if enable_enhancements and not synthetic_dataframe.empty:
        if params.get("enable_marginal_matching", True):
            synthetic_dataframe = apply_rank_preserving_marginal_matching(dataframe, synthetic_dataframe)
        if params.get("enable_categorical_matching", True):
            synthetic_dataframe = match_categorical_frequencies(dataframe, synthetic_dataframe)
        if params.get("enable_privacy_guard", True):
            synthetic_dataframe, _ = privacy_guard_filter(
                real_df=dataframe,
                synthetic_df=synthetic_dataframe,
                max_exact_duplicate_rate=float(params.get("max_exact_duplicate_rate", 0.01)),
            )

    # Final safety net: models can still emit NaN/blank values even when their
    # training input is complete. Reuse fill values learned from the exact
    # preprocessed training frame, then fail closed if any missing values remain.
    if not synthetic_dataframe.empty:
        synthetic_dataframe = handle_missing_values(
            synthetic_dataframe,
            reference_dataframe=dataframe,
        )
        if synthetic_dataframe.isna().any().any():
            missing_columns = synthetic_dataframe.columns[synthetic_dataframe.isna().any()].tolist()
            raise ValueError(
                "Generated dataset contains missing values after final imputation: "
                + ", ".join(map(str, missing_columns))
            )

    reporter.complete("sample")

    # ==================================================
    # 9. SAVE GENERATED DATASET
    # ==================================================

    reporter.complete("validate")
    reporter.start("save", message="Writing the synthetic dataset")

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
        file_name=generated_dataset["file_name"],
        file_path=generated_dataset["file_path"],
        row_count=generated_dataset["row_count"],
        column_count=generated_dataset["column_count"],
    )

    # ==================================================
    # 11. UPDATE STATUS
    # ==================================================

    update_generation_run_status(
        run_id=run_id,
        status="completed",
    )
    if job_id:
        update_generation_job_status(
            job_id=job_id,
            status="completed",
            result_id=result_id,
            stage_message=f"Completed {len(synthetic_dataframe)} rows successfully",
        )
        delete_checkpoint(job_id)

    reporter.complete("save")

    # ==================================================
    # 12. API RESPONSE
    # ==================================================

    return {
        "status": "success",
        "message": "Synthetic dataset generated successfully.",
        "data": {
            "run_id": run_id,
            "result_id": result_id,
            "dataset_id": dataset_id,
            "model_name": model_name,
            "parameters": parameters,
            "source_filename": filename,
            "configurations": configurations,
            "generated_dataset": generated_dataset,
            "business_rules": business_rules,
            "validation": {
                "target_row_count": target_row_count,
                "total_generated_rows": len(synthetic_dataframe),
                "total_valid_rows": len(synthetic_dataframe),
                "total_rejected_rows": 0,
                "attempts": current_batch_num or 1,
                "final_validation": {
                    "valid": True,
                    "valid_row_count": len(synthetic_dataframe),
                    "invalid_row_count": 0,
                    "invalid_rows": [],
                    "rules": [],
                },
            },
            "quality_enhancements": {
                "enabled": (parameters or {}).get("enable_quality_enhancements", True),
                "derived_features_enabled": (parameters or {}).get("enable_derived_features", True),
                "marginal_matching_enabled": (parameters or {}).get("enable_marginal_matching", True),
                "categorical_matching_enabled": (parameters or {}).get("enable_categorical_matching", True),
                "privacy_guard_enabled": (parameters or {}).get("enable_privacy_guard", True),
                "best_of_n": (parameters or {}).get("best_of_n", 1),
            },
        },
    }