def validate_referential_integrity(
    generated_tables: dict,
    relationships: list,
):
    results = []

    for relationship in relationships:

        parent_dataset_id = relationship["parent_dataset_id"]
        parent_column = relationship["parent_column"]

        child_dataset_id = relationship["child_dataset_id"]
        child_column = relationship["child_column"]

        parent_df = generated_tables[
            parent_dataset_id
        ]["dataframe"]

        child_df = generated_tables[
            child_dataset_id
        ]["dataframe"]

        parent_keys = set(
            parent_df[parent_column]
            .dropna()
            .tolist()
        )

        child_keys = set(
            child_df[child_column]
            .dropna()
            .tolist()
        )

        invalid_keys = child_keys - parent_keys

        results.append({
            "relationship_id": relationship[
                "relationship_id"
            ],
            "parent_dataset_id": parent_dataset_id,
            "child_dataset_id": child_dataset_id,
            "parent_column": parent_column,
            "child_column": child_column,
            "valid": len(invalid_keys) == 0,
            "invalid_key_count": len(invalid_keys),
            "invalid_keys": list(invalid_keys),
        })

    return {
        "valid": all(
            result["valid"]
            for result in results
        ),
        "relationships": results,
    }