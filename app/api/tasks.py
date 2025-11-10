"""Task queue API endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, List
from app.middleware.auth_middleware import get_current_user
from app.tasks.scraper_tasks import (
    scrape_spotify_task, scrape_youtube_task, 
    scrape_instagram_task, scrape_web_task,
    bulk_score_update_task, celery_app
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

class ScraperTaskRequest(BaseModel):
    task_type: str  # spotify, youtube, instagram, web
    priority: str = "normal"  # high, normal, low
    params: Dict

class BulkScoreTaskRequest(BaseModel):
    score_updates: List[Dict]

@router.post("/scrape")
async def queue_scraper_task(
    request: Request,
    task_request: ScraperTaskRequest,
    current_user: dict = Depends(get_current_user)
):
    """Queue a scraping task for background processing"""
    
    user_id = current_user["user_id"]
    task_type = task_request.task_type.lower()
    params = task_request.params
    
    # Set task priority
    priority_map = {"high": 9, "normal": 5, "low": 1}
    priority = priority_map.get(task_request.priority, 5)
    
    try:
        if task_type == "spotify":
            task = scrape_spotify_task.apply_async(
                kwargs={
                    "genre": params.get("genre", "hip-hop"),
                    "min_followers": params.get("min_followers", 500),
                    "limit": params.get("limit", 50),
                    "user_id": user_id
                },
                priority=priority
            )
        
        elif task_type == "youtube":
            task = scrape_youtube_task.apply_async(
                kwargs={
                    "query": params.get("query", "hip hop playlist"),
                    "max_results": params.get("max_results", 50),
                    "user_id": user_id
                },
                priority=priority
            )
        
        elif task_type == "instagram":
            task = scrape_instagram_task.apply_async(
                kwargs={
                    "hashtag": params.get("hashtag"),
                    "username": params.get("username"),
                    "user_id": user_id
                },
                priority=priority
            )
        
        elif task_type == "web":
            if not params.get("url"):
                raise HTTPException(status_code=400, detail="URL required for web scraping")
            
            task = scrape_web_task.apply_async(
                kwargs={
                    "url": params["url"],
                    "user_id": user_id
                },
                priority=priority
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown task type: {task_type}")
        
        return {
            "status": "queued",
            "task_id": task.id,
            "task_type": task_type,
            "estimated_completion": "5-15 minutes",
            "priority": task_request.priority
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")

@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get status of a background task"""
    
    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                "task_id": task_id,
                "status": "pending",
                "message": "Task is waiting to be processed"
            }
        elif task.state == 'PROGRESS':
            response = {
                "task_id": task_id,
                "status": "running",
                "progress": task.info.get('status', 'Processing...'),
                "meta": task.info
            }
        elif task.state == 'SUCCESS':
            response = {
                "task_id": task_id,
                "status": "completed",
                "result": task.result
            }
        else:  # FAILURE
            response = {
                "task_id": task_id,
                "status": "failed",
                "error": str(task.info)
            }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@router.post("/bulk-score-update")
async def queue_bulk_score_update(
    request: Request,
    task_request: BulkScoreTaskRequest,
    current_user: dict = Depends(get_current_user)
):
    """Queue bulk score update task"""
    
    user_id = current_user["user_id"]
    
    try:
        task = bulk_score_update_task.apply_async(
            kwargs={
                "score_updates": task_request.score_updates,
                "user_id": user_id
            }
        )
        
        return {
            "status": "queued",
            "task_id": task.id,
            "updates_count": len(task_request.score_updates)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue bulk update: {str(e)}")

@router.delete("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running task"""
    
    try:
        celery_app.control.revoke(task_id, terminate=True)
        
        return {
            "status": "cancelled",
            "task_id": task_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")

@router.get("/queue-status")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """Get overall queue status and statistics"""
    
    try:
        # Get active tasks
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        
        # Count tasks by queue
        queue_stats = {}
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    queue = task.get('delivery_info', {}).get('routing_key', 'default')
                    queue_stats[queue] = queue_stats.get(queue, 0) + 1
        
        return {
            "active_workers": len(active_tasks) if active_tasks else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
            "scheduled_tasks": sum(len(tasks) for tasks in scheduled_tasks.values()) if scheduled_tasks else 0,
            "queue_breakdown": queue_stats
        }
        
    except Exception as e:
        return {
            "error": f"Failed to get queue status: {str(e)}",
            "active_workers": 0,
            "active_tasks": 0
        }
