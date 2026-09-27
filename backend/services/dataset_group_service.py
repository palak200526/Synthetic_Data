from backend.repositories.dataset_group_repository import (
    create_dataset_group,
)


def create_group(
    group_name: str,
    domain_type: str | None = None,
    user_id: int | None = None,
):
    if not group_name or not group_name.strip():
        raise ValueError("Group name is required.")

    return create_dataset_group(
        group_name=group_name.strip(),
        domain_type=domain_type,
        user_id=user_id,
    )