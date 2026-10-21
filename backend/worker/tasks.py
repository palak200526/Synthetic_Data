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
    job_id=None,
    resume=False,
):
    """
    Background synthetic generation, including local LLM text columns.

    job_id / resume tie this run to a row in generation_jobs so checkpoints,
    pause/cancel requests and resume all work under Celery too.
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
            job_id=job_id,
            resume=resume,
        )
    except Exception as exc:
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise


@celery_app.task(
    bind=True,
    name="datrixa.generate_multi_table",
    max_retries=0,
)
def generate_multi_table_task(
    self,
    group_id: int,
    model_name: str,
    user_id: int,
    parameters=None,
    job_id=None,
    resume=False,
):
    """Background multi-table generation with per-table checkpoint/resume."""
    from backend.worker.generation_job import run_multi_table_generation
    from backend.repositories.generation_job_repository import update_generation_job_status

    def progress_update(state, meta):
        self.update_state(state=state, meta=meta)

    try:
        result = run_multi_table_generation(
            group_id=group_id,
            model_name=model_name,
            user_id=user_id,
            parameters=parameters,
            progress_update=progress_update,
            job_id=job_id,
            resume=resume,
        )
        if result.get("status") == "paused":
            update_generation_job_status(job_id=job_id, status="paused", stage_message="Paused after saving multi-table checkpoint")
        elif result.get("status") == "cancelled":
            update_generation_job_status(job_id=job_id, status="cancelled", stage_message="Multi-table generation cancelled")
        else:
            first_result = next((t.get("result_id") for t in result.get("tables", {}).values() if t.get("result_id")), None)
            update_generation_job_status(job_id=job_id, status="completed", result_id=first_result, stage_message="Multi-table generation completed")
            from backend.services.generation_checkpoint_service import delete_checkpoint
            delete_checkpoint(job_id)
        return result
    except Exception as exc:
        update_generation_job_status(job_id=job_id, status="failed", error_message=str(exc), stage_message="Multi-table generation failed")
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise
