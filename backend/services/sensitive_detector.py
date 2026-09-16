import re
import pandas as pd


SENSITIVE_KEYWORDS = [
    "name",
    "email",
    "phone",
    "mobile",
    "address",
    "dob",
    "date_of_birth",
    "birth",
    "gender",
    "salary",
    "income",
    "password",
    "ssn",
    "aadhaar",
    "aadhar",
    "pan",
    "credit_card",
]


IDENTIFIER_KEYWORDS = [
    "id",
    "identifier",
    "uuid",
    "user_id",
    "customer_id",
    "employee_id",
    "account_id",
    "transaction_id",
]


def detect_sensitive_and_identifier_columns(dataframe: pd.DataFrame):
    results = []

    for column in dataframe.columns:

        column_name = str(column).lower().strip()

        unique_ratio = (
            dataframe[column].nunique(dropna=True)
            / max(len(dataframe), 1)
        )

        is_sensitive = any(
            keyword in column_name
            for keyword in SENSITIVE_KEYWORDS
        )

        is_identifier = any(
            keyword in column_name
            for keyword in IDENTIFIER_KEYWORDS
        )

        # Detect common data patterns
        non_null_values = (
            dataframe[column]
            .dropna()
            .astype(str)
        )

        if len(non_null_values) > 0:

            email_matches = non_null_values.str.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            )

            if email_matches.mean() >= 0.8:
                is_sensitive = True

        results.append(
            {
                "column_name": column,
                "data_type": str(dataframe[column].dtype),
                "unique_ratio": round(unique_ratio, 4),
                "is_sensitive": is_sensitive,
                "is_identifier": is_identifier,
                "requires_review": is_sensitive or is_identifier,
            }
        )

    return results