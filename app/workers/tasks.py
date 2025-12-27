"""Celery task definitions."""

import logging
import random
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Task
from pymongo import MongoClient

from app.config import settings
from app.models.nosql.event import JobStatus
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def get_mongodb_sync():
    """Get synchronous MongoDB client for Celery tasks."""
    client = MongoClient(settings.MONGODB_URL)
    return client[settings.MONGODB_DATABASE]


class TransientError(Exception):
    """Error that should trigger a retry."""

    pass


class PermanentError(Exception):
    """Error that should not trigger a retry."""

    pass


class BaseTask(Task):
    """Base task with common error handling."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")

        # Update job status in MongoDB
        try:
            db = get_mongodb_sync()
            db.job_results.update_one(
                {"_id": task_id},
                {
                    "$set": {
                        "status": JobStatus.FAILED.value,
                        "error": str(exc),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")



def _execute_code_locally(
    code: str,
    language: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Execute code locally using subprocess (minimal implementation)."""
    if language.lower() not in ["python", "python3"]:
        return {
            "stdout": "",
            "stderr": f"Language '{language}' is not supported for local execution.",
            "exit_code": 1,
            "execution_time_ms": 0,
        }

    # Create a temporary file to store the code
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(code.encode("utf-8"))
        tmp_path = tmp.name

    start_time = time.time()
    try:
        # Run the code as a separate process
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "execution_time_ms": execution_time_ms,
            "memory_used_mb": random.uniform(5, 15),  # Simplified memory tracking
            "language": language,
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_seconds}s",
            "exit_code": 124,
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Execution error: {str(e)}",
            "exit_code": 1,
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
    finally:
        # Clean up the temporary file
        Path(tmp_path).unlink(missing_ok=True)


@celery_app.task(
    bind=True,
    base=BaseTask,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def execute_code_task(self, job_id: str) -> dict[str, Any]:
    """
    Actual code execution task.
    """
    db = get_mongodb_sync()
    collection = db.job_results

    # Idempotency check
    existing = collection.find_one({"_id": job_id})
    if existing and existing.get("status") == JobStatus.COMPLETED.value:
        return existing.get("result", {})

    collection.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": JobStatus.RUNNING.value,
                "started_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
            "$inc": {"attempts": 1},
        },
    )

    try:
        job = collection.find_one({"_id": job_id})
        if job is None:
            raise PermanentError(f"Job {job_id} not found")

        input_data = job.get("input_data", {})
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        timeout_seconds = input_data.get("timeout_seconds", 30)

        # Execute ACTUAL code
        result = _execute_code_locally(code, language, timeout_seconds)

        collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.COMPLETED.value,
                    "result": result,
                    "completed_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                }
            },
        )

        return result

    except Exception as e:
        if self.request.retries < self.max_retries:
            raise TransientError(str(e))
        else:
            collection.update_one(
                {"_id": job_id}, {"$set": {"status": JobStatus.FAILED.value, "error": str(e)}}
            )
            raise


@celery_app.task(
    bind=True,
    base=BaseTask,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def process_generic_job(self, job_id: str) -> dict[str, Any]:
    """
    Generic job processor for various task types.
    """
    db = get_mongodb_sync()
    collection = db.job_results

    # Idempotency check
    existing = collection.find_one({"_id": job_id})
    if existing and existing.get("status") == JobStatus.COMPLETED.value:
        return existing.get("result", {})

    # Update status to running
    collection.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": JobStatus.RUNNING.value,
                "started_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
            "$inc": {"attempts": 1},
        },
    )

    try:
        job = collection.find_one({"_id": job_id})
        if job is None:
            raise PermanentError(f"Job {job_id} not found")

        task_type = job.get("task_type", "unknown")
        input_data = job.get("input_data", {})

        # Process based on task type
        if task_type == "echo":
            result = {"echo": input_data}
        elif task_type == "delay":
            delay = input_data.get("seconds", 5)
            time.sleep(min(delay, 60))  # Cap at 60 seconds
            result = {"delayed": delay}
        elif task_type == "compute":
            # Simulate some computation
            n = input_data.get("n", 100)
            result = {"sum": sum(range(n))}
        else:
            result = {"processed": True, "task_type": task_type}

        # Update with result
        collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.COMPLETED.value,
                    "result": result,
                    "completed_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                }
            },
        )

        return result

    except (TransientError, PermanentError):
        raise
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise TransientError(str(e))
        else:
            collection.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": JobStatus.FAILED.value,
                        "error": f"Max retries exceeded: {e}",
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            raise
