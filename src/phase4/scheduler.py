# Phase 4 Implementation

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import hashlib

class PollingScheduler:
    def __init__(self):
        self.scheduled_tasks = {}
        self.task_locks = {}
        
    def schedule_task(self, source_id: str, run_at: datetime, task_type: str = "default"):
        """Schedule a task to run at a specific time"""
        task_id = hashlib.md5(f"{source_id}_{run_at}".encode()).hexdigest()[:8]
        self.scheduled_tasks[task_id] = {
            "source_id": source_id,
            "run_at": run_at,
            "task_type": task_type,
            "status": "scheduled"
        }
        return task_id
        
    def get_next_run_time(self, source_type: str = "default") -> datetime:
        """Calculate next run time based on source type"""
        # Default daily schedule
        if source_type == "default":
            # Run daily
            return datetime.now() + timedelta(days=1)
        elif source_type == "feed":
            # Run every 6 hours for feed sources
            return datetime.now() + timedelta(hours=6)
        else:
            # Run daily
            return datetime.now() + timedelta(days=1)
            
    def acquire_task_lock(self, task_id: str) -> bool:
        """Acquire a lock for a task to prevent duplicate processing"""
        if task_id in self.task_locks:
            if self.task_locks[task_id]["expires"] > time.time():
                return False  # Task already locked
        # Acquire lock for 1 hour
        self.task_locks[task_id] = {
            "expires": time.time() + 3600,
            "acquired_at": time.time()
        }
        return True
        
    def release_task_lock(self, task_id: str):
        """Release a task lock"""
        if task_id in self.task_locks:
            del self.task_locks[task_id]

class SourcePoliteness:
    def __init__(self):
        self.rate_limits = {}  # source_id -> requests_per_hour
        
    def check_rate_limit(self, source_id: str, max_requests: int = 100) -> bool:
        """Check if we're within rate limits for a source"""
        if source_id not in self.rate_limits:
            self.rate_limits[source_id] = 0
            
        if self.rate_limits[source_id] < max_requests:
            self.rate_limits[source_id] += 1
            return True
        return False

# Example usage
def main():
    scheduler = PollingScheduler()
    politeness = SourcePoliteness()
    
    # Schedule a task
    task_id = scheduler.schedule_task("source_1", 
                                     scheduler.get_next_run_time("feed"))
    
    # Check rate limit
    if politeness.check_rate_limit("source_1", 50):
        print("Within rate limits, can proceed with task")
    else:
        print("Rate limit exceeded, need to wait")

if __name__ == "__main__":
    main()