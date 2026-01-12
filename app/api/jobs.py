"""Job status API endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.middleware.auth_middleware import get_current_user
from app.workers.queue_adapter import get_job_status

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/status/{job_id}")
async def get_job_status_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get status of a background job"""
    try:
        status = get_job_status(job_id)
        
        if status.get("status") == "unknown":
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@router.get("/queues")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """Get status of all queues"""
    try:
        from app.workers.queue_adapter import get_active_queues
        return get_active_queues()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")