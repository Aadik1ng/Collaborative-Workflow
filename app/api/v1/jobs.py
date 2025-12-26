"""Job processing endpoints."""

from datetime import datetime, timezone
from math import ceil
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.db.mongodb import get_job_results_collection
from app.models.nosql.event import JobResult, JobStatus
from app.models.sql.user import User
from app.schemas.job import (
    CodeExecutionJobCreate,
    JobCancelResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
)
from app.workers.celery_app import celery_app

router = APIRouter()


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new job",
)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Submit a new job for async processing."""
    collection = get_job_results_collection()

    # Generate job ID (use idempotency key if provided)
    job_id = job_data.idempotency_key or str(uuid4())

    # Check for existing job with same idempotency key
    if job_data.idempotency_key:
        existing = await collection.find_one({"_id": job_id})
        if existing:
            return JobResponse(**JobResult.from_mongo(existing).model_dump())

    # Create job record
    job = JobResult(
        id=job_id,
        user_id=str(current_user.id),
        task_type=job_data.task_type,
        status=JobStatus.PENDING,
        input_data=job_data.input_data,
    )

    await collection.insert_one(job.to_mongo())

    # Submit to Celery
    celery_app.send_task(
        "app.workers.tasks.process_generic_job",
        args=[job_id],
        task_id=job_id,
    )

    return JobResponse(**job.model_dump())


@router.post(
    "/code-execution",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit code for execution",
)
async def create_code_execution_job(
    job_data: CodeExecutionJobCreate,
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Submit code for async execution."""
    collection = get_job_results_collection()

    job_id = str(uuid4())

    job = JobResult(
        id=job_id,
        user_id=str(current_user.id),
        task_type="code_execution",
        status=JobStatus.PENDING,
        input_data={
            "code": job_data.code,
            "language": job_data.language,
            "timeout_seconds": job_data.timeout_seconds,
            "memory_limit_mb": job_data.memory_limit_mb,
        },
    )

    await collection.insert_one(job.to_mongo())

    # Submit to Celery
    celery_app.send_task(
        "app.workers.tasks.execute_code_task",
        args=[job_id],
        task_id=job_id,
    )

    return JobResponse(**job.model_dump())


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Get job status and result."""
    collection = get_job_results_collection()

    job_doc = await collection.find_one({"_id": job_id})

    if job_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    job = JobResult.from_mongo(job_doc)

    # Verify ownership
    if job.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this job",
        )

    return JobResponse(**job.model_dump())


@router.get(
    "",
    response_model=JobListResponse,
    summary="List user's jobs",
)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[JobStatus] = None,
    current_user: User = Depends(get_current_user),
) -> JobListResponse:
    """List all jobs for the current user."""
    collection = get_job_results_collection()

    query = {"user_id": str(current_user.id)}
    if status_filter:
        query["status"] = status_filter.value

    # Get total count
    total = await collection.count_documents(query)

    # Get paginated results
    cursor = collection.find(query).sort("created_at", -1)
    cursor = cursor.skip((page - 1) * page_size).limit(page_size)

    jobs = []
    async for doc in cursor:
        jobs.append(JobResponse(**JobResult.from_mongo(doc).model_dump()))

    return JobListResponse(
        items=jobs,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total > 0 else 1,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel a job",
)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> JobCancelResponse:
    """Cancel a pending or running job."""
    collection = get_job_results_collection()

    job_doc = await collection.find_one({"_id": job_id})

    if job_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    job = JobResult.from_mongo(job_doc)

    # Verify ownership
    if job.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this job",
        )

    # Check if cancellable
    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status {job.status.value}",
        )

    # Revoke Celery task
    celery_app.control.revoke(job_id, terminate=True)

    # Update status
    await collection.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": JobStatus.CANCELLED.value,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return JobCancelResponse(
        id=job_id,
        status=JobStatus.CANCELLED,
        message="Job cancelled successfully",
    )
