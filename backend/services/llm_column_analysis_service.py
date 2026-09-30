import json
import ollama

from backend.schemas.llm_analysis_schema import (
    LLMAnalysisResponse,
)


MODEL_NAME = "qwen3:4b"


SYSTEM_PROMPT = """
You analyze dataset column profiles for synthetic data generation.

For EVERY input column, return exactly one result.

Determine:

1. is_identifier
2. action
3. reason

Do NOT rely only on the column name.

Use the complete profile, including:

- dtype
- row_count
- unique_count
- unique_ratio
- null_count
- null_ratio
- sample_values
- string_length
- patterns
- statistics
- top_values

Possible actions:

keep:
Generate the column normally.

remove:
Exclude the column from the synthetic dataset.

new_id:
The column is an identifier. Generate new synthetic identifier values.

generalize:
Generate a less specific representation of the original values.

derived:
Calculate the column after other columns are generated.

Important:

A column being unique does NOT automatically make it an identifier.
Use the complete column profile to make the decision.

Return ALL input columns.

Return exactly one analysis for every input column.

Keep each reason short and concise.
"""


def analyze_columns(
    column_profiles: list[dict],
) -> LLMAnalysisResponse:

    user_prompt = f"""
Analyze ALL of these dataset column profiles.

{json.dumps(column_profiles, indent=2, default=str)}

Return exactly one result for EVERY input column.
Do not skip any column.
Keep reasons short.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        format=LLMAnalysisResponse.model_json_schema(),
        think=False,
        options={
            "num_ctx": 8192,
            "temperature": 0,
        },
    )

    result = response["message"]["content"]

    return LLMAnalysisResponse.model_validate_json(result)