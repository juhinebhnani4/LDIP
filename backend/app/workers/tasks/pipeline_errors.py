"""Custom exceptions for pipeline task chain error propagation.

When a chained pipeline task hits a terminal failure (max retries exhausted,
non-retryable error), it should raise one of these exceptions AFTER performing
its own cleanup (_mark_job_failed, _release_pipeline_lock_safe).

Celery sees the exception → chain stops immediately → link_error callback
fires as a safety net for any cleanup the task missed.

This replaces the old pattern of returning {"status": "..._failed", ...} dicts,
which Celery treated as success (see P7 in ARCH-PATTERNS.md).
"""


class PipelineTaskError(Exception):
    """Raised by chained document pipeline tasks on terminal failure.

    Celery sees this as a task failure, which stops the chain.
    Carries context needed by the link_error safety-net callback.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "PIPELINE_TASK_FAILED",
        document_id: str | None = None,
        job_id: str | None = None,
        matter_id: str | None = None,
        stage: str | None = None,
    ):
        self.error_code = error_code
        self.document_id = document_id
        self.job_id = job_id
        self.matter_id = matter_id
        self.stage = stage
        super().__init__(message)


class LibraryPipelineTaskError(Exception):
    """Raised by chained library pipeline tasks on terminal failure.

    Same purpose as PipelineTaskError but for the library document pipeline
    (chunk_library_document → embed_library_chunks → fire_library_callbacks).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "LIBRARY_PIPELINE_TASK_FAILED",
        library_document_id: str | None = None,
    ):
        self.error_code = error_code
        self.library_document_id = library_document_id
        super().__init__(message)
