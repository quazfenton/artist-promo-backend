"""
Tests for queue adapter

Run with: pytest tests/test_queue_adapter.py -v
"""
import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.workers.queue_adapter import (
    enqueue_job,
    dequeue_job,
    complete_job,
    fail_job,
    fingerprint,
    get_job_status,
    get_queue_length,
    push_to_dead_letter
)


class TestQueueAdapter:
    """Test queue adapter functionality"""
    
    def test_enqueue_job(self, mock_redis):
        """Test job enqueueing"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            job_id = enqueue_job(
                job_type="scrape:spotify_playlist",
                params={"genre": "hip-hop"},
                source="api",
                priority=5
            )
            
            assert job_id is not None
            assert len(job_id) == 36  # UUID length
            mock_redis.lpush.assert_called_once()
            mock_redis.hset.assert_called_once()
    
    def test_enqueue_job_with_dedupe(self, mock_redis):
        """Test job enqueueing with deduplication"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            # First enqueue
            job_id1 = enqueue_job(
                job_type="scrape:spotify_playlist",
                params={"genre": "hip-hop"},
                dedupe_key="test-dedupe-key"
            )
            
            # Second enqueue with same dedupe key should return same job_id
            job_id2 = enqueue_job(
                job_type="scrape:spotify_playlist",
                params={"genre": "hip-hop"},
                dedupe_key="test-dedupe-key"
            )
            
            assert job_id1 == job_id2
    
    def test_fingerprint_consistency(self):
        """Test fingerprint generation is consistent"""
        payload1 = {
            "type": "scrape:spotify",
            "params": {"genre": "hip-hop"}
        }
        
        payload2 = {
            "type": "scrape:spotify",
            "params": {"genre": "hip-hop"}
        }
        
        # Same payload should produce same fingerprint
        fp1 = fingerprint(payload1)
        fp2 = fingerprint(payload2)
        
        assert fp1 == fp2
    
    def test_fingerprint_uniqueness(self):
        """Test different payloads produce different fingerprints"""
        payload1 = {
            "type": "scrape:spotify",
            "params": {"genre": "hip-hop"}
        }
        
        payload2 = {
            "type": "scrape:spotify",
            "params": {"genre": "rap"}
        }
        
        fp1 = fingerprint(payload1)
        fp2 = fingerprint(payload2)
        
        assert fp1 != fp2
    
    def test_get_job_status_unknown(self, mock_redis):
        """Test getting status of unknown job"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            mock_redis.hget.return_value = None
            
            status = get_job_status("unknown-job-id")
            
            assert status["status"] == "unknown"
            assert status["job_id"] == "unknown-job-id"
    
    def test_complete_job(self, mock_redis):
        """Test marking job as complete"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            result = {"success": True, "count": 10}
            complete_job("test-job-id", result)
            
            mock_redis.hset.assert_called_once()
            
            # Verify the data structure
            call_args = mock_redis.hset.call_args
            job_data = json.loads(call_args[0][1])
            
            assert job_data["status"] == "completed"
            assert job_data["result"] == result
            assert "completed" in job_data
    
    def test_fail_job(self, mock_redis):
        """Test marking job as failed"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            fail_job("test-job-id", "Test error message")
            
            mock_redis.hset.assert_called_once()
            
            # Verify the data structure
            call_args = mock_redis.hset.call_args
            job_data = json.loads(call_args[0][1])
            
            assert job_data["status"] == "failed"
            assert job_data["error"] == "Test error message"
            assert "failed" in job_data
    
    def test_push_to_dead_letter(self, mock_redis):
        """Test pushing job to dead letter queue"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            job = {"job_id": "test-job", "type": "scrape:spotify"}
            push_to_dead_letter(job, "Fatal error")
            
            mock_redis.lpush.assert_called_once()
            
            # Verify the data structure
            call_args = mock_redis.lpush.call_args
            dead_letter_data = json.loads(call_args[0][1])
            
            assert dead_letter_data["job"] == job
            assert dead_letter_data["error"] == "Fatal error"
            assert "timestamp" in dead_letter_data
    
    def test_get_queue_length(self, mock_redis):
        """Test getting queue length"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            mock_redis.llen.return_value = 5
            
            length = get_queue_length("queue:scrape")
            
            assert length == 5
            mock_redis.llen.assert_called_once_with("queue:scrape")


class TestDequeueJob:
    """Test job dequeueing"""
    
    def test_dequeue_job_with_data(self):
        """Test dequeueing job when queue has data"""
        with patch('app.workers.queue_adapter.r') as mock_redis:
            job_data = {
                "job_id": "test-job",
                "type": "scrape:spotify",
                "params": {"genre": "hip-hop"}
            }
            
            mock_redis.brpop.return_value = ("queue:scrape", json.dumps(job_data))
            
            job = dequeue_job("queue:scrape", timeout=5)
            
            assert job is not None
            assert job["job_id"] == "test-job"
            assert job["type"] == "scrape:spotify"
    
    def test_dequeue_job_empty_queue(self):
        """Test dequeueing from empty queue"""
        with patch('app.workers.queue_adapter.r') as mock_redis:
            mock_redis.brpop.return_value = None
            
            job = dequeue_job("queue:scrape", timeout=5)
            
            assert job is None


class TestJobLifecycle:
    """Test complete job lifecycle"""
    
    def test_job_lifecycle(self, mock_redis):
        """Test complete job lifecycle: enqueue -> dequeue -> complete"""
        with patch('app.workers.queue_adapter.r', mock_redis):
            # Enqueue job
            job_id = enqueue_job(
                job_type="scrape:spotify_playlist",
                params={"genre": "hip-hop", "min_followers": 1000}
            )
            
            # Verify job was queued
            assert job_id is not None
            
            # Mock dequeue
            job_data = {
                "job_id": job_id,
                "type": "scrape:spotify_playlist",
                "params": {"genre": "hip-hop", "min_followers": 1000}
            }
            mock_redis.brpop.return_value = ("queue:scrape", json.dumps(job_data))
            
            # Dequeue job
            job = dequeue_job("queue:scrape")
            assert job is not None
            assert job["job_id"] == job_id
            
            # Complete job
            result = {"success": True, "count": 50}
            complete_job(job_id, result)
            
            # Verify completion
            mock_redis.hset.assert_called()
