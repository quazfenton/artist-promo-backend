"""Comprehensive health check system"""
from fastapi import APIRouter
from sqlalchemy import create_engine, text
from typing import Dict, Any
import redis
import aiohttp
import asyncio
import time
import os
from datetime import datetime

router = APIRouter()

class HealthChecker:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            engine = create_engine(self.database_url, pool_pre_ping=True)  # Enable connection health checks

            with engine.connect() as conn:
                # Test basic connectivity
                conn.execute(text("SELECT 1"))

                # Test table access
                result = conn.execute(text("SELECT COUNT(*) FROM contacts WHERE deleted_at IS NULL"))
                contact_count = result.scalar()

                # Test write operation (in a transaction that we rollback)
                trans = conn.begin()
                try:
                    conn.execute(text("INSERT INTO contacts (full_name, contact_type) VALUES ('Health Check', 'user')"))
                    conn.execute(text("DELETE FROM contacts WHERE full_name = 'Health Check'"))
                    trans.rollback()  # Rollback the test transaction
                except Exception:
                    if trans:
                        trans.rollback()
                    raise

                response_time = (time.time() - start_time) * 1000

                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "contact_count": contact_count,
                    "connection_pool_size": engine.pool.size(),
                    "checked_out_connections": engine.pool.checkedout(),
                    "pool_status": {
                        "size": engine.pool.size(),
                        "checkedout_count": engine.pool.checkedout(),
                        "overflow": getattr(engine.pool, 'overflow', 'N/A')
                    }
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = time.time()
            r = redis.from_url(self.redis_url)

            # Test basic connectivity
            r.ping()

            # Test read/write with a unique key to avoid conflicts
            import uuid
            test_key = f"health_check_test_{uuid.uuid4().hex}"
            r.set(test_key, "test_value", ex=60)
            value = r.get(test_key)
            r.delete(test_key)

            # Verify the value we got back
            if value != b"test_value":
                return {
                    "status": "unhealthy",
                    "error": "Redis read/write test failed - value mismatch",
                    "response_time_ms": None
                }

            response_time = (time.time() - start_time) * 1000

            # Get Redis info
            info = r.info()

            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "memory_usage_mb": round(info.get('used_memory', 0) / 1024 / 1024, 2),
                "connected_clients": info.get('connected_clients', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "memory_peak_mb": round(info.get('used_memory_peak', 0) / 1024 / 1024, 2),
                "evicted_keys": info.get('evicted_keys', 0)
            }
        except redis.ConnectionError as e:
            return {
                "status": "unhealthy",
                "error": f"Redis connection error: {str(e)}",
                "response_time_ms": None
            }
        except redis.TimeoutError as e:
            return {
                "status": "unhealthy",
                "error": f"Redis timeout error: {str(e)}",
                "response_time_ms": None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Redis error: {str(e)}",
                "response_time_ms": None
            }
    
    async def check_external_apis(self) -> Dict[str, Any]:
        """Check external API connectivity"""
        apis_to_check = [
            ("Spotify", "https://api.spotify.com/v1/"),
            ("Hunter.io", "https://api.hunter.io/v2/"),
        ]
        
        results = {}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for api_name, url in apis_to_check:
                try:
                    start_time = time.time()
                    async with session.get(url) as response:
                        response_time = (time.time() - start_time) * 1000
                        
                        results[api_name.lower()] = {
                            "status": "healthy" if response.status < 500 else "degraded",
                            "response_time_ms": round(response_time, 2),
                            "status_code": response.status
                        }
                except Exception as e:
                    results[api_name.lower()] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "response_time_ms": None
                    }
        
        return results
    
    async def check_celery_workers(self) -> Dict[str, Any]:
        """Check Celery worker status"""
        try:
            from app.tasks.scraper_tasks import celery_app
            
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            stats = inspect.stats()
            
            if not active_tasks:
                return {
                    "status": "unhealthy",
                    "error": "No active workers found",
                    "worker_count": 0
                }
            
            worker_count = len(active_tasks)
            total_active_tasks = sum(len(tasks) for tasks in active_tasks.values())
            
            return {
                "status": "healthy",
                "worker_count": worker_count,
                "active_tasks": total_active_tasks,
                "workers": list(active_tasks.keys())
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "worker_count": 0
            }

health_checker = HealthChecker()

@router.get("/health")
async def basic_health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with all dependencies"""
    
    start_time = time.time()
    
    # Run all health checks concurrently
    database_check, redis_check, api_check, worker_check = await asyncio.gather(
        health_checker.check_database(),
        health_checker.check_redis(),
        health_checker.check_external_apis(),
        health_checker.check_celery_workers(),
        return_exceptions=True
    )
    
    total_time = (time.time() - start_time) * 1000
    
    # Determine overall status
    checks = {
        "database": database_check,
        "redis": redis_check,
        "external_apis": api_check,
        "celery_workers": worker_check
    }
    
    # Calculate overall health
    unhealthy_services = []
    for service, check in checks.items():
        if isinstance(check, Exception):
            unhealthy_services.append(service)
        elif check.get("status") == "unhealthy":
            unhealthy_services.append(service)
    
    overall_status = "unhealthy" if unhealthy_services else "healthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "response_time_ms": round(total_time, 2),
        "checks": checks,
        "unhealthy_services": unhealthy_services
    }

@router.get("/health/readiness")
async def readiness_check():
    """Kubernetes readiness probe"""
    
    # Check critical dependencies only
    db_check = await health_checker.check_database()
    
    if db_check.get("status") != "healthy":
        return {"status": "not_ready", "reason": "database_unavailable"}
    
    return {"status": "ready"}

@router.get("/health/liveness")
async def liveness_check():
    """Kubernetes liveness probe"""
    
    # Simple check to ensure the application is running
    try:
        # Test basic functionality
        current_time = time.time()
        return {
            "status": "alive",
            "timestamp": current_time,
            "uptime_seconds": current_time - start_time if 'start_time' in globals() else 0
        }
    except Exception:
        return {"status": "dead"}

# Store application start time
start_time = time.time()
