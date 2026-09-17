from backend.repositories.configuration_repository import (
    save_configuration,
)


def save_column_configurations(request):
    saved_configurations = []

    for configuration in request.configurations:
        result = save_configuration(
            configuration
        )
        saved_configurations.append(result)

    return {
        "status": "success",
        "message": "Column classifications saved successfully.",
        "data": saved_configurations,
    }