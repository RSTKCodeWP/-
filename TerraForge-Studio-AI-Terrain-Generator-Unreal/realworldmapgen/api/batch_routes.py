"""
Batch Processing API Routes
Handles batch terrain generation and queue management
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..core.generator_provider import get_generator
from ..core.queue_manager import BatchJob, JobStatus, queue_manager
from ..models import MapGenerationRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchRequest(BaseModel):
    """Request to add jobs to batch queue"""
    jobs: List[MapGenerationRequest]
    priority: int = 0


class BatchResponse(BaseModel):
    """Response when creating batch"""
    batch_id: str
    job_ids: List[str]
    total: int


@router.post("/add", response_model=BatchResponse)
async def add_batch_jobs(
    request: BatchRequest,
    background_tasks: BackgroundTasks
):
    """
    Add multiple jobs to the batch queue

    Args:
        request: Batch request with list of generation requests

    Returns:
        Batch response with job IDs
    """
    if not request.jobs:
        raise HTTPException(status_code=400, detail="No jobs provided")

    if len(request.jobs) > queue_manager.max_queue_size:
        raise HTTPException(
            status_code=400,
            detail=f"Too many jobs (max: {queue_manager.max_queue_size})"
        )

    job_ids = []

    for gen_request in request.jobs:
        try:
            # Validate request
            area_km2 = gen_request.bbox.area_km2()
            if area_km2 <= 0:
                logger.warning(f"Skipping invalid bbox for {gen_request.name}")
                continue

            # Add to queue
            job = await queue_manager.add_job(
                request=gen_request.model_dump(mode="json"),
                name=gen_request.name,
                priority=request.priority
            )

            job_ids.append(job.id)

        except Exception as e:
            logger.error(f"Failed to queue job {gen_request.name}: {e}")

    # Start processing jobs in background
    background_tasks.add_task(process_queue)

    return BatchResponse(
        batch_id=f"batch_{len(job_ids)}",
        job_ids=job_ids,
        total=len(job_ids)
    )


async def process_queue():
    """Background task to process queued jobs"""
    while queue_manager.can_process_more():
        job = await queue_manager.get_next_job()

        if not job:
            break  # No more pending jobs

        logger.info(f"Starting batch job {job.id}: {job.name}")

        try:
            # Mark as started
            await queue_manager.start_job(job.id)

            gen_request = MapGenerationRequest(**job.request)

            # Mirror generation progress onto the queue job so /api/batch/jobs
            # and the queue UI show real progress instead of a bar stuck at 0.
            async def report_progress(progress: float, _step: str, job_id: str = job.id):
                await queue_manager.update_job_progress(
                    job_id, progress, JobStatus.PROCESSING
                )

            # Run generation on the shared generator so the job is also
            # visible through /api/tasks.
            result = await get_generator().generate_terrain(
                gen_request,
                task_id=job.id,
                on_progress=report_progress,
            )

            if result.status == JobStatus.FAILED.value:
                await queue_manager.fail_job(job.id, result.error or "Generation failed")
            else:
                await queue_manager.complete_job(job.id, result.model_dump(mode="json"))

        except Exception as e:
            logger.error(f"Batch job {job.id} failed: {e}")
            await queue_manager.fail_job(job.id, str(e))

        # A failing job must not stop the rest of the queue, so the loop
        # always continues to the next pending job.


@router.get("/jobs", response_model=List[BatchJob])
async def list_batch_jobs(status: Optional[str] = None):
    """
    List all batch jobs, optionally filtered by status

    Args:
        status: Optional status filter (pending, processing, completed, failed)
    """
    job_status = None
    if status:
        try:
            job_status = JobStatus(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status}"
            ) from exc

    jobs = await queue_manager.list_jobs(status=job_status)
    return jobs


@router.get("/jobs/{job_id}", response_model=BatchJob)
async def get_batch_job(job_id: str):
    """Get a specific batch job"""
    job = await queue_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_batch_job(job_id: str):
    """Cancel a batch job"""
    success = await queue_manager.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be cancelled (not found or already completed)"
        )

    return {"success": True, "message": f"Job {job_id} cancelled"}


@router.post("/jobs/{job_id}/retry")
async def retry_batch_job(job_id: str, background_tasks: BackgroundTasks):
    """Retry a failed batch job"""
    success = await queue_manager.retry_job(job_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be retried (not found or not failed)"
        )

    # Start processing
    background_tasks.add_task(process_queue)

    return {"success": True, "message": f"Job {job_id} queued for retry"}


@router.get("/stats")
async def get_queue_stats():
    """Get queue statistics"""
    return await queue_manager.get_queue_stats()


@router.post("/clear")
async def clear_completed_jobs():
    """Clear completed and failed jobs from history"""
    count = await queue_manager.clear_completed()
    return {"success": True, "cleared": count}


@router.post("/process")
async def trigger_processing(background_tasks: BackgroundTasks):
    """Manually trigger queue processing"""
    background_tasks.add_task(process_queue)
    return {"success": True, "message": "Queue processing triggered"}


@router.get("/downloads/{job_id}")
async def get_batch_downloads(job_id: str):
    """Get download links for completed batch job"""
    job = await queue_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed (status: {job.status})"
        )

    if not job.result:
        raise HTTPException(status_code=500, detail="Job has no result")

    # GenerationResult.exports is a list of per-format outcomes; only the
    # successful ones have downloadable files.
    terrain_name = job.result.get("terrain_name", job.name)
    downloads = [
        {
            "format": export.get("format"),
            "url": f"/api/maps/{terrain_name}/download/zip",
            "files": export.get("files", {}),
        }
        for export in job.result.get("exports", [])
        if export.get("success")
    ]

    return {
        "job_id": job.id,
        "name": job.name,
        "downloads": downloads,
        "completed_at": job.completed_at
    }

