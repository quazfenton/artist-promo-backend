"""Job status API endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.middleware.auth_middleware import get_current_user
from app.workers.queue_adapter import (
    get_job_status,
    get_active_queues,
    get_queue_length,
    r
)
from app.models.database import SessionLocal
from app.models.staging import JobTracker, ScraperRawSignal, StagingContact, ResolvedEntity
from sqlalchemy import func

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/status/{job_id}")
async def get_job_status_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed status of a background job
    
    Returns comprehensive job information including:
    - Queue status (queued, running, completed, failed)
    - Pipeline progress (raw signals, staging contacts, resolved entities)
    - Timing information
    - Error details if failed
    """
    try:
        db = SessionLocal()
        
        # Get queue status
        queue_status = get_job_status(job_id)
        
        if queue_status.get("status") == "unknown":
            # Check database tracker
            tracker = db.query(JobTracker).filter(JobTracker.job_id == job_id).first()
            if tracker:
                queue_status = {
                    "status": tracker.status,
                    "job_id": job_id,
                    "job_type": tracker.job_type,
                    "created": tracker.created_at.isoformat() if tracker.created_at else None,
                    "started": tracker.started_at.isoformat() if tracker.started_at else None,
                    "completed": tracker.completed_at.isoformat() if tracker.completed_at else None,
                    "error": tracker.error_message,
                    "result": tracker.result,
                }
            else:
                raise HTTPException(status_code=404, detail="Job not found")
        
        # Enrich with pipeline progress
        raw_signal_count = db.query(ScraperRawSignal).filter(
            ScraperRawSignal.job_id == job_id
        ).count()
        
        staging_count = 0
        if raw_signal_count > 0:
            raw_signals = db.query(ScraperRawSignal.id).filter(
                ScraperRawSignal.job_id == job_id
            ).all()
            raw_signal_ids = [rs.id for rs in raw_signals]
            
            staging_count = db.query(StagingContact).filter(
                StagingContact.raw_signal_id.in_(raw_signal_ids)
            ).count()
        
        # Get resolved entity count (if we can track back to job)
        resolved_count = 0
        if staging_count > 0:
            staging_ids = db.query(StagingContact.id).filter(
                StagingContact.raw_signal_id.in_(raw_signal_ids)
            ).all()
            # This is approximate since resolved entities merge multiple staging contacts
            resolved_count = db.query(ResolvedEntity).count()  # Simplified
        
        queue_status["pipeline_progress"] = {
            "raw_signals": raw_signal_count,
            "staging_contacts": staging_count,
            "resolved_entities": resolved_count,
        }
        
        return queue_status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")
    finally:
        db.close()


@router.get("/queues")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """
    Get status of all queues
    
    Returns:
    - Queue names and lengths
    - Active job counts
    - Dead letter queue size
    """
    try:
        queues = get_active_queues()
        
        # Add dead letter queue info
        dead_letter_count = get_queue_length("queue:dead_letter")
        
        return {
            "active_queues": queues,
            "dead_letter_queue": dead_letter_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")


@router.get("/list")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (pending, running, completed, failed)"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List jobs with filtering and pagination
    """
    try:
        db = SessionLocal()
        
        query = db.query(JobTracker)
        
        if status:
            query = query.filter(JobTracker.status == status)
        
        if job_type:
            query = query.filter(JobTracker.job_type.like(f"%{job_type}%"))
        
        total = query.count()
        jobs = query.order_by(JobTracker.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "jobs": [
                {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "error_message": job.error_message,
                }
                for job in jobs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")
    finally:
        db.close()


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retry a failed job
    
    Only jobs with status 'failed' can be retried.
    """
    try:
        db = SessionLocal()
        
        tracker = db.query(JobTracker).filter(JobTracker.job_id == job_id).first()
        
        if not tracker:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if tracker.status != "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry job with status '{tracker.status}'. Only failed jobs can be retried."
            )
        
        # Re-enqueue the job
        from app.workers.queue_adapter import enqueue_job
        
        # Extract original job parameters
        if tracker.result and isinstance(tracker.result, dict):
            params = tracker.result.get("params", {})
        else:
            params = {}
        
        # Add error history
        params["_retry_count"] = params.get("_retry_count", 0) + 1
        params["_previous_error"] = tracker.error_message
        
        new_job_id = enqueue_job(
            job_type=tracker.job_type,
            params=params,
            source="retry",
            priority=5,
        )
        
        # Update tracker
        tracker.status = "pending"
        tracker.error_message = None
        tracker.started_at = None
        
        db.commit()
        
        return {
            "message": "Job queued for retry",
            "original_job_id": job_id,
            "new_job_id": new_job_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")
    finally:
        db.close()


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a running or pending job
    
    Note: This only marks the job as cancelled in the tracker.
    The actual worker process would need to check for cancellation.
    """
    try:
        db = SessionLocal()
        
        tracker = db.query(JobTracker).filter(JobTracker.job_id == job_id).first()
        
        if not tracker:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if tracker.status in ["completed", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status '{tracker.status}'"
            )
        
        # Mark as failed with cancellation reason
        tracker.status = "failed"
        tracker.error_message = "Cancelled by user"
        tracker.completed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "Job cancelled",
            "job_id": job_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")
    finally:
        db.close()