import os
import pandas as pd

from backend.services.multi_table_generation_service import (
    generate_linked_tables,
)
from backend.services.referential_integrity_service import (
    validate_referential_integrity,
)


def test_multi_table_generation_and_relationships():
    group_id = 3

    result = generate_linked_tables(
        group_id=group_id,
        model_name="gaussian_copula",
        parameters={"random_state": 42},
    )

    # 1. Group validation
    assert result["group_id"] == group_id

    # 2. Expected tables
    expected_dataset_ids = {124, 125, 137, 138}
    actual_dataset_ids = set(result["tables"].keys())

    assert actual_dataset_ids == expected_dataset_ids

    # 3. Generated files exist
    for dataset_id, table in result["tables"].items():
        assert os.path.exists(table["file_path"])
        assert table["row_count"] > 0
        assert table["column_count"] > 0

    # 4. Referential integrity
    validation = validate_referential_integrity(
        result["tables"],
        result["relationships"],
    )

    assert validation["valid"] is True

    # 5. No invalid foreign keys
    for relationship in validation["relationships"]:
        assert relationship["valid"] is True
        assert relationship["invalid_key_count"] == 0

    # 6. Supplier relationship
    supplier_parent = result["tables"][124]["dataframe"]
    supplier_child = result["tables"][125]["dataframe"]

    assert supplier_child["supplier_id"].isin(
        supplier_parent["supplier_id"]
    ).all()

    # 7. Product relationship
    product_parent = result["tables"][137]["dataframe"]
    product_child = result["tables"][138]["dataframe"]

    assert product_child["product_id"].isin(
        product_parent["product_id"]
    ).all()