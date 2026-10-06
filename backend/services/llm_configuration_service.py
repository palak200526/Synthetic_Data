from backend.services.llm_column_analysis_service import (
    analyze_columns,
)

from backend.services.dataset_profiler import (
    generate_profile,
)

from backend.schemas.configuration_schema import (
    ColumnConfiguration,
)

from backend.repositories.configuration_repository import (
    save_configuration,
    save_configurations_bulk,
)


def build_column_configurations(
    dataframe,
    dataset_id: int
):
    """
    Generate column configurations using
    dataset profiling + LLM analysis.
    """

    # ---------------------------------------------------------
    # 1. Generate dataset profile
    # ---------------------------------------------------------

    profile = generate_profile(dataframe)

    column_profiles = profile.get("columns", [])

    # ---------------------------------------------------------
    # 2. Run LLM analysis
    # ---------------------------------------------------------

    llm_result = analyze_columns(
        column_profiles
    )

    # ---------------------------------------------------------
    # 3. Convert LLM output into ColumnConfiguration objects
    # ---------------------------------------------------------

    configurations = []

    for analysis in llm_result.columns:

        column_type = _get_column_type(
            column_profiles,
            analysis.column_name
        )

        is_id = True if analysis.action == "new_id" else analysis.is_identifier

        configuration = ColumnConfiguration(
            dataset_id=dataset_id,
            column_name=analysis.column_name,
            column_type=column_type,
            is_identifier=is_id,
            action=analysis.action,
            rule=None,
        )

        configurations.append(
            configuration
        )

    return configurations


def _get_column_type(
    column_profiles: list[dict],
    column_name: str
):
    for column in column_profiles:
        if column.get("column_name") == column_name:
            return (
                column.get("classification")
                or column.get("dtype")
                or column.get("type")
                or "string"
            )

    return "string"


def save_llm_configurations(
    dataframe,
    dataset_id: int
):
    """
    Generate column configurations using the LLM
    and save them into PostgreSQL.
    """

    configurations = build_column_configurations(
        dataframe,
        dataset_id
    )

    return save_configurations_bulk(
        dataset_id=dataset_id,
        configurations=configurations,
    )