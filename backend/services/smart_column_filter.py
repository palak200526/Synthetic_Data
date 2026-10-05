"""
Rule-based pre-classification for obvious columns and heuristic fallback.
These rules provide fast classification and robust fallback when Ollama is unreachable.
"""

from __future__ import annotations

import re

# Columns that are obviously auto-generated features (f0, f1, f609, etc.)
_FEATURE_PATTERN = re.compile(r"^f\d+$", re.IGNORECASE)

# Columns that look like IDs
_ID_NAMES = {
    "id",
    "uuid",
    "guid",
    "pk",
    "identifier",
    "key",
    "user_id",
    "user id",
    "userid",
    "customer_id",
    "customer id",
    "customerid",
    "order_id",
    "order id",
    "orderid",
    "product_id",
    "product id",
    "productid",
    "supplier_id",
    "supplier id",
    "supplierid",
    "session_id",
    "session id",
    "account_id",
    "account id",
}

_TEXT_NAME_HINTS = (
    "text",
    "content",
    "body",
    "tweet",
    "caption",
    "post",
    "feedback",
    "comment",
    "comments",
    "review",
    "reviews",
    "description",
    "complaint",
    "complaints",
    "remark",
    "remarks",
    "reason",
    "message",
    "messages",
    "note",
    "notes",
    "summary",
    "narrative",
    "sentence",
    "paragraph",
    "document",
)


def is_freeform_text_profile(profile: dict) -> bool:
    """
    True when a column looks like free-form natural language
    rather than a short categorical/code field.
    """
    name_lower = (profile.get("column_name") or "").strip().lower()
    dtype = (profile.get("dtype") or "").lower()
    unique_ratio = float(profile.get("unique_ratio") or 0.0)
    patterns = profile.get("patterns") or []
    length_info = profile.get("string_length") or {}
    avg_len = float(length_info.get("average") or 0.0)

    if any(p in {"email", "phone", "uuid"} for p in patterns):
        return False

    is_stringish = any(
        token in dtype
        for token in ("object", "string", "str", "category")
    ) or dtype == ""

    if not is_stringish:
        return False

    # Check if column name contains text hints
    hinted = any(hint in name_lower for hint in _TEXT_NAME_HINTS)
    if hinted:
        return True

    # If average string length is long, it's free-form text
    if avg_len >= 15:
        return True

    if avg_len >= 8 and unique_ratio >= 0.3:
        return True

    return False


def is_obvious_column(profile: dict) -> dict | None:
    """
    Return a hardcoded recommendation if the column is obvious.
    Return None if the column needs deeper LLM analysis.
    """
    name = (profile.get("column_name") or "").strip()
    name_lower = name.lower()

    unique_count = profile.get("unique_count", 0)
    unique_ratio = float(profile.get("unique_ratio", 0.0) or 0.0)
    null_ratio = float(profile.get("null_ratio", 0.0) or 0.0)
    dtype = (profile.get("dtype") or "").lower()

    # ---------------------------------------------------------
    # Rule 1: Unnamed / index columns → REMOVE
    # ---------------------------------------------------------
    if (
        name_lower.startswith("unnamed")
        or name_lower in ("index", "level_0", "level_1")
        or name_lower == ""
    ):
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "remove",
            "reason": "Unnamed or index column.",
        }

    # ---------------------------------------------------------
    # Rule 2: >95% null → REMOVE
    # ---------------------------------------------------------
    if null_ratio > 0.95:
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "remove",
            "reason": "Column is almost entirely empty.",
        }

    # ---------------------------------------------------------
    # Rule 3: Constant column → REMOVE
    # ---------------------------------------------------------
    if unique_count <= 1 and null_ratio < 1.0:
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "remove",
            "reason": "Constant column with no variance.",
        }

    # ---------------------------------------------------------
    # Rule 4: Auto-generated feature names (f0, f1, ..., f617) → KEEP
    # ---------------------------------------------------------
    if _FEATURE_PATTERN.match(name):
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "keep",
            "reason": "Numeric feature column.",
        }

    # ---------------------------------------------------------
    # Rule 5: Clear ID columns → NEW_ID
    # ---------------------------------------------------------
    if (
        name_lower in _ID_NAMES
        or name_lower.endswith("_id")
        or name_lower.endswith(" id")
        or name_lower.endswith("_key")
        or name_lower.endswith(" key")
    ):
        return {
            "column_name": name,
            "is_identifier": True,
            "action": "new_id",
            "reason": "Identifier column. Regenerate unique IDs.",
        }

    # ---------------------------------------------------------
    # Rule 6: Free-form text → LLM generation
    # ---------------------------------------------------------
    if is_freeform_text_profile(profile):
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "llm",
            "reason": "Free-form text column. Use local LLM generation.",
        }

    # ---------------------------------------------------------
    # No rule matched → needs LLM or heuristic fallback
    # ---------------------------------------------------------
    return None


def heuristic_column_analysis(profile: dict) -> dict:
    """
    Fallback classifier that provides an accurate decision for any column
    when the local LLM service is offline or unreachable.
    """
    obvious = is_obvious_column(profile)
    if obvious is not None:
        return obvious

    name = (profile.get("column_name") or "").strip()
    name_lower = name.lower()
    dtype = (profile.get("dtype") or "").lower()
    unique_ratio = float(profile.get("unique_ratio", 0.0) or 0.0)

    # Freeform text
    if is_freeform_text_profile(profile):
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "llm",
            "reason": "Free-form text column. Use local LLM generation.",
        }

    # Identifier
    if unique_ratio > 0.85 and ("int" in dtype or "str" in dtype or "obj" in dtype) and ("id" in name_lower or "code" in name_lower or "num" in name_lower):
        return {
            "column_name": name,
            "is_identifier": True,
            "action": "new_id",
            "reason": "High-cardinality identifier column.",
        }

    # Temporal / Datetime
    if any(token in dtype for token in ("date", "time")):
        return {
            "column_name": name,
            "is_identifier": False,
            "action": "keep",
            "reason": "Temporal column. Preserve date distribution.",
        }

    # Standard tabular / numeric / categorical column
    return {
        "column_name": name,
        "is_identifier": False,
        "action": "keep",
        "reason": "Standard feature column. Model with generative distribution.",
    }