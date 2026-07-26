"""
Queue Manager for Batch Processing
Handles multiple terrain generation tasks with priority queuing
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of a batch job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchJob(BaseModel):
    """Represents a single job in the batch queue"""
    id: str
    name: str
    request: dict  # MapGenerationRequest as dict
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 0  # Higher = more priority

    class Config:
        use_enum_values = True


class BatchQueueManager:
    """
    Manages a queue of terrain generation jobs
    Supports priority queuing and concurrent processing
    """

    def __init__(self, max_concurrent: int = 3, max_queue_size: int = 50):
        """
        Initialize the queue manager

        Args:
            max_concurrent: Maximum number of jobs to process concurrently
            max_queue_size: Maximum number of jobs in queue
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.jobs: Dict[str, BatchJob] = {}
        self.queue: List[str] = []  # Job IDs in order
        self.active_jobs: set = set()
        self.processing_lock = asyncio.Lock()

    async def add_job(
        self,
        request: dict,
        name: str,
        priority: int = 0
    ) -> BatchJob:
        """
        Add a new job to the queue

        Args:
            request: Terrain generation request
            name: Job name
            priority: Job priority (higher = processed first)

        Returns:
            Created batch job

        Raises:
            ValueError: If queue is full
        """
        if len(self.queue) >= self.max_queue_size:
            raise ValueError(f"Queue is full (max: {self.max_queue_size})")

        job_id = str(uuid.uuid4())

        job = BatchJob(
            id=job_id,
            name=name,
            request=request,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            priority=priority
        )

        self.jobs[job_id] = job

        # Insert based on priority
        insert_pos = 0
        for i, existing_id in enumerate(self.queue):
            if self.jobs[existing_id].priority < priority:
                insert_pos = i
                break
            insert_pos = i + 1

        self.queue.insert(insert_pos, job_id)

        logger.info(f"Added job {job_id} to queue (priority: {priority}, position: {insert_pos})")

        return job

    async def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or processing job

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False if not found or already completed
        """
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            return False

        job.status = JobStatus.CANCELLED

        if job_id in self.queue:
            self.queue.remove(job_id)

        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)

        logger.info(f"Cancelled job {job_id}")
        return True

    async def update_job_progress(
        self,
        job_id: str,
        progress: float,
        status: Optional[JobStatus] = None
    ):
        """Update job progress and optionally status"""
        job = self.jobs.get(job_id)
        if job:
            job.progress = progress
            if status:
                job.status = status

            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.now()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.now()
                if job_id in self.active_jobs:
                    self.active_jobs.remove(job_id)

    async def get_next_job(self) -> Optional[BatchJob]:
        """Get next job to process (highest priority pending job)"""
        async with self.processing_lock:
            for job_id in self.queue:
                job = self.jobs[job_id]
                if job.status == JobStatus.PENDING:
                    return job
            return None

    async def start_job(self, job_id: str):
        """Mark job as started"""
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()
            self.active_jobs.add(job_id)

    async def complete_job(self, job_id: str, result: dict):
        """Mark job as completed with result"""
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.result = result
            job.completed_at = datetime.now()

            if job_id in self.active_jobs:
                self.active_jobs.remove(job_id)

            if job_id in self.queue:
                self.queue.remove(job_id)

            logger.info(f"Completed job {job_id}")

    async def fail_job(self, job_id: str, error: str):
        """Mark job as failed"""
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = error
            job.completed_at = datetime.now()

            if job_id in self.active_jobs:
                self.active_jobs.remove(job_id)

            if job_id in self.queue:
                self.queue.remove(job_id)

            logger.error(f"Failed job {job_id}: {error}")

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None
    ) -> List[BatchJob]:
        """
        List all jobs, optionally filtered by status

        Args:
            status: Optional status filter

        Returns:
            List of jobs
        """
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending
        jobs.sort(key=lambda x: x.created_at, reverse=True)

        return jobs

    async def get_queue_stats(self) -> dict:
        """Get queue statistics"""
        total = len(self.jobs)
        pending = sum(1 for j in self.jobs.values() if j.status == JobStatus.PENDING)
        processing = len(self.active_jobs)
        completed = sum(1 for j in self.jobs.values() if j.status == JobStatus.COMPLETED)
        failed = sum(1 for j in self.jobs.values() if j.status == JobStatus.FAILED)

        return {
            "total_jobs": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "queue_length": len(self.queue),
            "active_jobs": list(self.active_jobs),
            "max_concurrent": self.max_concurrent,
            "max_queue_size": self.max_queue_size
        }

    async def clear_completed(self) -> int:
        """Clear completed and failed jobs from history"""
        to_remove = [
            job_id for job_id, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
        ]

        for job_id in to_remove:
            del self.jobs[job_id]

        logger.info(f"Cleared {len(to_remove)} completed/failed jobs")
        return len(to_remove)

    def can_process_more(self) -> bool:
        """Check if we can process more jobs (not at max concurrent)"""
        return len(self.active_jobs) < self.max_concurrent

    async def retry_job(self, job_id: str) -> bool:
        """
        Retry a failed job

        Args:
            job_id: Job ID to retry

        Returns:
            True if queued for retry, False otherwise
        """
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.FAILED:
            return False

        job.status = JobStatus.PENDING
        job.progress = 0.0
        job.error = None
        job.started_at = None
        job.completed_at = None

        # Add back to queue with same priority
        self.queue.append(job_id)

        logger.info(f"Retrying job {job_id}")
        return True


# Global queue manager instance
queue_manager = BatchQueueManager(max_concurrent=3, max_queue_size=50)

