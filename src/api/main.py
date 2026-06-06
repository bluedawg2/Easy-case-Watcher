# Enhanced FastAPI Implementation

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import hashlib
from contextlib import asynccontextmanager
from src.models.models import get_db, Source, Change, ChangeStatus, SourceStatus
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables
    from src.models.models import create_tables
    create_tables()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down application")

app = FastAPI(title="Bankruptcy Rule Monitor API", lifespan=lifespan)

class PhaseAnalysisRequest(BaseModel):
    phase_id: str
    requirements: List[str]

class ImplementationRequest(BaseModel):
    analysis: Dict[str, Any]

class ReviewRequest(BaseModel):
    implementation: Dict[str, Any]

class ValidationRequest(BaseModel):
    implementation: Dict[str, Any]

class SourceResponse(BaseModel):
    id: int
    name: str
    url: str
    jurisdiction: str
    layer: str

class ChangeResponse(BaseModel):
    id: int
    content: str
    detected_date: datetime
    effective_date: datetime
    status: str

@app.get("/")
async def root():
    return {"message": "Bankruptcy Rule Monitor API - Monitoring U.S. bankruptcy rule changes across 94 federal judicial districts"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/analyze-phase/{phase_id}")
async def analyze_phase(phase_id: str, requirements: PhaseAnalysisRequest):
    """Analyze a phase using Pete (Product Manager)"""
    try:
        # This would call the actual Pete agent in production
        logger.info(f"Analyzing phase {phase_id}")
        return {"analysis": f"Analysis completed for {phase_id}"}
    except Exception as e:
        logger.error(f"Error analyzing phase: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sources")
async def list_sources():
    """List all monitored sources"""
    try:
        # This would query the actual database in production
        sources = [
            {"id": 1, "name": "Northern District of Georgia", "url": "https://ndga.uscourts.gov", "jurisdiction": "federal", "layer": "district"},
            {"id": 2, "name": "Eastern District of California", "url": "https://caed.uscourts.gov", "jurisdiction": "federal", "layer": "district"}
        ]
        return sources
    except Exception as e:
        logger.error(f"Error listing sources: {str(e)}")
        raise HTTPException(status_code=500, de
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/changes")
async def get_changes():
    """Get recent changes"""
    try:
        # This would query the actual database in production
        changes = [
            {"id": 1, "content": "New rule change in Northern District", "detected_date": "2026-06-01", "effective_date": "2026-06-15", "status": "pending"},
            {"id": 2, "content": "Fee schedule update", "detected_date": "2026-06-02", "effective_date": "2026-06-16", "status": "active"}
        ]
        return changes
    except Exception as e:
        logger.error(f"Error getting changes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")