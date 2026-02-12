"""
Small adapter to enqueue jobs into Redis (RQ/Celery adapter can be swapped).
This is intentionally minimal — adapt to your chosen queue library.
"""
import json
import uuid
from datetime import datetime
import redis
import os
from typing import Dict, Any, Optional
import hashlib

# Get Redis URL from environment, with fallback
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def enqueue_job(job_type: str, params: dict, source: str = "api", priority: int = 5, dedupe_key: str = None, user_id: int = None) -> str:
    """
    Enqueue a job into the appropriate Redis queue
    
    Args:
        job_type: Type of job (e.g., "scrape:spotify_playlist", "normalize:signals")
        params: Job-specific parameters
        source: Source of the job (api, cli, n8n)
        priority: Priority level (1-9)
        dedupe_key: Key to prevent duplicate jobs
        user_id: ID of user who triggered the job
    
    Returns:
        job_id: Unique identifier for the job
    """
    job = {
        "job_id": str(uuid.uuid4()),
        "type": job_type,
        "source": source,
        "params": params,
        "priority": priority,
        "dedupe_key": dedupe_key,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id
    }

    # Check for duplicate job if dedupe_key is provided
    if dedupe_key:
        # Create a fingerprint of the job to check if it's already been queued/completed
        fp = fingerprint(job)
        existing_job_id = get_job_id_by_fingerprint(fp)
        if existing_job_id:
            return existing_job_id
        # No mapping found; log warning and continue to enqueue a new job
        logging.getLogger(__name__).warning(
            "Fingerprint %s seen before but no job_id mapping found", fp
        )

            # No mapping found; continue to enqueue a new job
            logging.getLogger(__name__).warning(
                f"Fingerprint seen but no job_id mapping found; fingerprint={fp}, job_type={job_type}, params={params}; re-enqueueing"
            )
    # Add priority to the job for prioritized processing
    job['priority'] = priority

    # Push job to Redis list
    r.lpush(queue_name, json.dumps(job))
    # Track the job in our job tracker
    r.hset("jobs", job["job_id"], json.dumps({
        "status": "queued",
        "queue": queue_name,
        "created": datetime.utcnow().isoformat() + "Z",
        "type": job_type
    }))
    
    # If dedupe_key is provided, mark this job as seen
    if dedupe_key:
        mark_seen(fp, job["job_id"])
    
    return job["job_id"]

def fingerprint(payload: Dict[str, Any]) -> str:
    """
    Create a fingerprint of a job payload for idempotency
    """
    # Create a hash of the job payload to detect duplicates
    # We'll exclude the job_id and created_at since those are unique per job
    payload_copy = payload.copy()
    payload_copy.pop('job_id', None)
    payload_copy.pop('created_at', None)
    
    raw = json.dumps(payload_copy, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def seen_before(fp: str) -> bool:
    """
    Check if we've seen a job with this fingerprint before
    """
    # Use sorted set with timestamp scores for TTL-like behavior
    return r.zscore("job_fingerprints", fp) is not None

def mark_seen(fp: str, job_id: str = None):
    """
    Mark a job fingerprint as seen
    """
    # Store with timestamp score, allowing cleanup of old entries
    r.zadd("job_fingerprints", {fp: datetime.utcnow().timestamp()})
    # Also store the mapping between fingerprint and job_id if provided
    if job_id:
        r.set(f"fingerprint_to_job_id:{fp}", job_id)

def cleanup_old_fingerprints(days_to_keep: int = 30):
    """Remove fingerprints older than specified days"""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days_to_keep)).timestamp()
    r.zremrangebyscore("job_fingerprints", "-inf", cutoff)

def get_job_id_by_fingerprint(fp: str) -> Optional[str]:
    """
    Get the job_id associated with a fingerprint
    """
    return r.get(f"fingerprint_to_job_id:{fp}")

def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a job
    """
    job_status = r.hget("jobs", job_id)
    if job_status:
        return json.loads(job_status)
    return {"status": "unknown", "job_id": job_id}

def dequeue_job(queue_name: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Dequeue a job from the specified queue
    """
    item = r.brpop(queue_name, timeout=timeout)
    if not item:
        return None
    _, payload = item
    return json.loads(payload)

def complete_job(job_id: str, result: Dict[str, Any]):
    """
    Mark a job as completed
    """
    r.hset("jobs", job_id, json.dumps({
        "status": "completed",
        "result": result,
        "completed": datetime.utcnow().isoformat() + "Z"
    }))

def fail_job(job_id: str, error: str):
    """
    Mark a job as failed
    """
    r.hset("jobs", job_id, json.dumps({
        "status": "failed",
        "error": error,
        "failed": datetime.utcnow().isoformat() + "Z"
    }))

def push_to_dead_letter(job: Dict[str, Any], error: str):
    """
    Push a failed job to the dead letter queue
    """
    dead_letter_item = {
        "job": job,
        "error": error,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    r.lpush("queue:dead_letter", json.dumps(dead_letter_item))

def get_queue_length(queue_name: str) -> int:
    """
    Get the length of a queue
    """
    return r.llen(queue_name)

def get_active_queues() -> Dict[str, int]:
    """
    Get lengths of all active queues
    """
    queues = {}
    for key in r.scan_iter("queue:*"):
        if key != "queue:dead_letter":  # Exclude dead letter queue from active queues
            queues[key] = r.llen(key)
    return queues