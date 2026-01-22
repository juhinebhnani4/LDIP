"""API routes for RAG evaluation framework.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Provides endpoints for evaluating RAG quality and managing golden datasets.
All endpoints enforce matter isolation.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status

from app.api.deps import get_matter_service
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.evaluation import (
    AddGoldenItemRequest,
    BatchEvaluateRequest,
    EvaluateRequest,
    EvaluateResponse,
    EvaluationResultsResponse,
    GoldenDatasetResponse,
    GoldenItemResponse,
    UpdateGoldenItemRequest,
)
from app.services.evaluation.golden_dataset import GoldenDatasetService
from app.services.evaluation.models import GoldenDatasetItem
from app.services.evaluation.ragas_evaluator import get_ragas_evaluator
from app.services.matter_service import MatterService
from app.services.supabase.client import get_supabase_client as get_supabase

router = APIRouter(prefix="/matters/{matter_id}/evaluation", tags=["evaluation"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _verify_matter_access(
    matter_id: str,
    user_id: str,
    matter_service: MatterService,
    require_edit: bool = False,
) -> None:
    """Verify user has access to matter.

    Args:
        matter_id: Matter UUID.
        user_id: User UUID.
        matter_service: Matter service instance.
        require_edit: If True, require OWNER or EDITOR role.

    Raises:
        HTTPException: If access denied.
    """
    role = matter_service.get_user_role(matter_id, user_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "MATTER_NOT_FOUND",
                    "message": "Matter not found or you don't have access",
                    "details": {},
                }
            },
        )

    if require_edit and role not in ("owner", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": "Owner or Editor role required",
                    "details": {},
                }
            },
        )


# =============================================================================
# Evaluation Endpoints
# =============================================================================


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_qa_pair(
    matter_id: str = Path(..., description="Matter UUID"),
    body: EvaluateRequest = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> EvaluateResponse:
    """Evaluate a single QA pair using RAGAS metrics.

    Returns faithfulness, answer relevancy, and optionally context recall
    (if ground_truth is provided).

    Cost Warning: Uses GPT-4 for evaluation (~$0.10-0.50 per evaluation).

    Args:
        matter_id: Matter UUID.
        body: Evaluation request with question, answer, contexts.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Evaluation result with RAGAS metric scores.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service, require_edit=True)

    logger.info(
        "evaluate_qa_pair_request",
        matter_id=matter_id,
        user_id=current_user.id,
        question_length=len(body.question),
        context_count=len(body.contexts),
        has_ground_truth=body.ground_truth is not None,
    )

    try:
        evaluator = get_ragas_evaluator()

        result = await evaluator.evaluate_single(
            question=body.question,
            answer=body.answer,
            contexts=body.contexts,
            ground_truth=body.ground_truth,
        )

        # Optionally store result in database
        if body.save_result:
            supabase = get_supabase()
            supabase.table("evaluation_results").insert({
                "matter_id": matter_id,
                "question": body.question,
                "answer": body.answer,
                "contexts": body.contexts,
                "context_recall": result.scores.context_recall,
                "faithfulness": result.scores.faithfulness,
                "answer_relevancy": result.scores.answer_relevancy,
                "overall_score": result.overall_score,
                "triggered_by": "manual",
            }).execute()

        return EvaluateResponse(data=result)

    except Exception as e:
        logger.error(
            "evaluate_qa_pair_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "EVALUATION_FAILED",
                    "message": str(e),
                    "details": {},
                }
            },
        ) from e


@router.post("/evaluate/batch")
async def evaluate_batch(
    matter_id: str = Path(..., description="Matter UUID"),
    body: BatchEvaluateRequest = ...,
    background_tasks: BackgroundTasks = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """Trigger batch evaluation of golden dataset items.

    Runs asynchronously via Celery. Results are stored in evaluation_results table.

    Args:
        matter_id: Matter UUID.
        body: Batch evaluation request with optional tag filters.
        background_tasks: FastAPI background tasks.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Task ID and status.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service, require_edit=True)

    logger.info(
        "evaluate_batch_request",
        matter_id=matter_id,
        user_id=current_user.id,
        tags=body.tags,
    )

    # Queue as Celery task for async processing
    from app.workers.tasks.evaluation_tasks import run_batch_evaluation

    task = run_batch_evaluation.delay(
        matter_id=matter_id,
        tags=body.tags,
        user_id=current_user.id,
    )

    return {
        "data": {
            "task_id": task.id,
            "status": "queued",
            "message": "Batch evaluation started. Results will be stored in evaluation_results.",
        }
    }


@router.get("/results", response_model=EvaluationResultsResponse)
async def get_evaluation_results(
    matter_id: str = Path(..., description="Matter UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    triggered_by: str | None = Query(None, description="Filter by trigger type"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> EvaluationResultsResponse:
    """Get historical evaluation results.

    Args:
        matter_id: Matter UUID.
        page: Page number (1-indexed).
        per_page: Items per page.
        triggered_by: Optional filter (manual, auto, batch).
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Paginated list of evaluation results.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    supabase = get_supabase()

    query = (
        supabase.table("evaluation_results")
        .select("*", count="exact")
        .eq("matter_id", matter_id)
    )

    if triggered_by:
        query = query.eq("triggered_by", triggered_by)

    offset = (page - 1) * per_page
    result = query.order("evaluated_at", desc=True).range(offset, offset + per_page - 1).execute()

    total = result.count or 0
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return EvaluationResultsResponse(
        data=result.data,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )


# =============================================================================
# Golden Dataset Endpoints
# =============================================================================


@router.get("/golden-dataset", response_model=GoldenDatasetResponse)
async def get_golden_dataset(
    matter_id: str = Path(..., description="Matter UUID"),
    tags: str | None = Query(None, description="Comma-separated tags to filter"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> GoldenDatasetResponse:
    """Get golden dataset items for a matter.

    Args:
        matter_id: Matter UUID.
        tags: Optional comma-separated tags to filter.
        page: Page number (1-indexed).
        per_page: Items per page.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Paginated list of golden dataset items.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    service = GoldenDatasetService()
    tag_list = tags.split(",") if tags else None

    offset = (page - 1) * per_page
    items = await service.get_items(
        matter_id=matter_id,
        tags=tag_list,
        limit=per_page,
        offset=offset,
    )

    # Get total count
    total = await service.count_items(matter_id)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return GoldenDatasetResponse(
        data=[item.model_dump() for item in items],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )


@router.post("/golden-dataset", response_model=GoldenItemResponse)
async def add_golden_item(
    matter_id: str = Path(..., description="Matter UUID"),
    body: AddGoldenItemRequest = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> GoldenItemResponse:
    """Add a QA pair to the golden dataset.

    Args:
        matter_id: Matter UUID.
        body: Golden item data (question, expected_answer, tags).
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Created golden dataset item.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service, require_edit=True)

    service = GoldenDatasetService()

    item = GoldenDatasetItem(
        matter_id=matter_id,
        question=body.question,
        expected_answer=body.expected_answer,
        relevant_chunk_ids=body.relevant_chunk_ids or [],
        tags=body.tags or [],
        created_by=current_user.id,
    )

    created = await service.add_item(item)

    logger.info(
        "golden_item_created",
        matter_id=matter_id,
        item_id=created.id,
        user_id=current_user.id,
    )

    return GoldenItemResponse(data=created.model_dump())


@router.get("/golden-dataset/{item_id}", response_model=GoldenItemResponse)
async def get_golden_item(
    matter_id: str = Path(..., description="Matter UUID"),
    item_id: str = Path(..., description="Item UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> GoldenItemResponse:
    """Get a specific golden dataset item.

    Args:
        matter_id: Matter UUID.
        item_id: Item UUID.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Golden dataset item.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    service = GoldenDatasetService()
    item = await service.get_item(item_id, matter_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "GOLDEN_ITEM_NOT_FOUND",
                    "message": "Golden dataset item not found",
                    "details": {},
                }
            },
        )

    return GoldenItemResponse(data=item.model_dump())


@router.patch("/golden-dataset/{item_id}", response_model=GoldenItemResponse)
async def update_golden_item(
    matter_id: str = Path(..., description="Matter UUID"),
    item_id: str = Path(..., description="Item UUID"),
    body: UpdateGoldenItemRequest = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> GoldenItemResponse:
    """Update a golden dataset item.

    Args:
        matter_id: Matter UUID.
        item_id: Item UUID.
        body: Fields to update.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Updated golden dataset item.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service, require_edit=True)

    service = GoldenDatasetService()

    updates = body.model_dump(exclude_unset=True)
    item = await service.update_item(item_id, matter_id, updates)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "GOLDEN_ITEM_NOT_FOUND",
                    "message": "Golden dataset item not found",
                    "details": {},
                }
            },
        )

    logger.info(
        "golden_item_updated",
        matter_id=matter_id,
        item_id=item_id,
        user_id=current_user.id,
    )

    return GoldenItemResponse(data=item.model_dump())


@router.delete("/golden-dataset/{item_id}")
async def delete_golden_item(
    matter_id: str = Path(..., description="Matter UUID"),
    item_id: str = Path(..., description="Item UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """Delete a golden dataset item.

    Args:
        matter_id: Matter UUID.
        item_id: Item UUID.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Deletion confirmation.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service, require_edit=True)

    service = GoldenDatasetService()
    deleted = await service.delete_item(item_id, matter_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "GOLDEN_ITEM_NOT_FOUND",
                    "message": "Golden dataset item not found",
                    "details": {},
                }
            },
        )

    logger.info(
        "golden_item_deleted",
        matter_id=matter_id,
        item_id=item_id,
        user_id=current_user.id,
    )

    return {"data": {"deleted": True, "id": item_id}}
