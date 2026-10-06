from backend.worker.celery_app import celery_app
from backend.worker.column_analysis_job import run_column_analysis
from backend.worker.generation_job import run_generation


@celery_app.task(
    bind=True,
    name="datrixa.analyze_columns",
    max_retries=2,
)
def analyze_columns_task(self, dataset_id: int, user_id: int):
    """
    Background task: analyze all dataset columns using LLM in batches.
    Reports progress as it goes.
    """

    def progress_update(state, meta):
        self.update_state(state=state, meta=meta)

    return run_column_analysis(dataset_id, user_id, progress_update)


@celery_app.task(
    bind=True,
    name="datrixa.generate_dataset",
    max_retries=0,
)
def generate_dataset_task(
    self,
    dataset_id: int,
    model_name: str,
    user_id: int,
    parameters=None,
):
    """
    Background synthetic generation, including local LLM text columns.
    """

    def progress_update(state, meta):
        self.update_state(state=state, meta=meta)

    try:
        return run_generation(
            dataset_id=dataset_id,
            model_name=model_name,
            user_id=user_id,
            parameters=parameters,
            progress_update=progress_update,
        )
    except Exception as exc:
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise
