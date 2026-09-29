import os
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.models import (
    Incident, RetainPayload, FeedbackRequest, LearnedPattern,
    MemoryTimelineEvent, InvestigationResult, ScoreboardMetric
)
from backend.memory.hindsight_adapter import hindsight
from backend.memory.memory_bank import payments_memory_bank
from backend.db.database import db

app = FastAPI(
    title="IncidentIQ Backend API",
    description="Self-learning DevOps Incident Response Agent powered by Hindsight Memory",
    version="1.0.0"
)

# Enable CORS for local Vite development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecallRequestBody(BaseModel):
    bank_id: Optional[str] = "team-payments"
    service: str = "payment-service"
    error_signature: str
    deploy_info: Optional[str] = None
    top_k: int = 5

class ResetRequestBody(BaseModel):
    bank_id: Optional[str] = "team-payments"

@app.on_event("startup")
async def startup():
    """
    On application startup:
    1. Ensure the live Hindsight server is active on port 8888.
    2. Connect the official Hindsight client.
    3. Asynchronously seed Stage 5 via await hindsight.aretain_batch(...) to avoid nested event loop conflicts.
    """
    try:
        from backend.memory.hindsight_server import ensure_server_running
        from backend.seed import init_bank_clean, build_seed_items
        ensure_server_running(port=8888)
        hindsight.connect_live()

        init_bank_clean(settings.HINDSIGHT_BANK_ID)
        seed_items = build_seed_items(stage=5)
        if seed_items:
            await hindsight.aretain_batch(bank_id=settings.HINDSIGHT_BANK_ID, items=seed_items)
        payments_memory_bank.reflect_patterns()
    except Exception as e:
        print(f"[Startup Warning] {e}")

@app.get("/api/health")
def health_check():
    # Dynamically verify live connection so banner is never stale
    hindsight.connect_live()
    return {
        "status": "healthy",
        "service": "IncidentIQ",
        "environment": settings.ENVIRONMENT_NAME,
        "hindsight_bank": settings.HINDSIGHT_BANK_ID,
        "hindsight_server_url": settings.HINDSIGHT_URL,
        "hindsight_live_connected": hindsight.is_live_connected,
        "llm_provider": settings.LLM_PROVIDER,
        "persisted_memories_count": hindsight.get_memories_count(settings.HINDSIGHT_BANK_ID)
    }

@app.post("/api/memory/retain")
def retain_memory(payload: RetainPayload):
    """
    Store an incident summary, symptoms, log signature, root cause, fix, and outcome in Hindsight.
    """
    res = payments_memory_bank.retain_incident(
        incident=Incident(
            id=payload.incident_id,
            timestamp="",
            service=payload.metadata.get("service", "payment-service"),
            severity=payload.metadata.get("severity", "P1-CRITICAL"),
            alert_text=payload.summary,
            logs=[payload.log_signature],
            metrics={"memory_rss_bytes": 0, "memory_limit_bytes": 0, "cpu_percent": 0, "p99_latency_ms": 0},  # type: ignore
            root_cause=payload.suspected_cause,
            recommended_fix=payload.fix_applied,
            engineer_name=payload.engineer_name,
            outcome=payload.outcome  # type: ignore
        ),
        fix_applied=payload.fix_applied,
        outcome=payload.outcome,
        engineer_feedback=payload.engineer_feedback,
        engineer_name=payload.engineer_name
    )
    return res

@app.post("/api/memory/recall")
def recall_memories(body: RecallRequestBody):
    """
    Recall relevant past incidents, error patterns, and policies from Hindsight.
    """
    memories = payments_memory_bank.recall_for_alert(
        service=body.service,
        error_signature=body.error_signature,
        deploy_info=body.deploy_info,
        top_k=body.top_k
    )
    return {
        "bank_id": body.bank_id or settings.HINDSIGHT_BANK_ID,
        "query": f"{body.service} {body.error_signature} {body.deploy_info or ''}".strip(),
        "total_matches": len(memories),
        "results": memories
    }

@app.post("/api/memory/reflect")
def trigger_reflect():
    """
    Triggers Hindsight cross-incident reflection to generate Learned Patterns.
    """
    patterns = payments_memory_bank.reflect_patterns()
    return {
        "status": "success",
        "patterns_count": len(patterns),
        "patterns": patterns
    }

@app.get("/api/memory/timeline")
def get_memory_timeline():
    """
    Returns live audit timeline of Hindsight retain/recall/reflect calls for the UI panel.
    """
    return hindsight.get_timeline()

@app.get("/api/memory/patterns")
def get_learned_patterns():
    """
    Returns current active learned patterns in Hindsight memory.
    """
    return payments_memory_bank.reflect_patterns()

@app.get("/api/memory/policies")
def get_team_policies():
    """
    Returns active team operational policies stored in Hindsight.
    """
    return hindsight.get_policies(settings.HINDSIGHT_BANK_ID)

@app.post("/api/memory/reset")
def reset_memory_bank(body: Optional[ResetRequestBody] = None):
    """
    Resets the memory bank to empty for demonstration cold starts.
    """
    bank_id = (body and body.bank_id) or settings.HINDSIGHT_BANK_ID
    hindsight.reset_bank(bank_id)
    db.reset_evals()
    return {"status": "reset_successful", "bank_id": bank_id}

@app.post("/api/feedback")
def submit_feedback(body: FeedbackRequest):
    """
    Process engineer Accept / Reject / Edit action and retain into Hindsight.
    """
    db.record_feedback(
        incident_id=body.incident_id,
        action=body.action,
        edited_fix=body.edited_fix,
        feedback=body.engineer_feedback,
        engineer_name=body.engineer_name
    )

    if body.mark_as_obsolete:
        res = payments_memory_bank.mark_fix_obsolete(
            incident_id=body.incident_id,
            reason=body.obsolete_reason or "Marked obsolete by engineer",
            engineer_name=body.engineer_name
        )
    else:
        res = payments_memory_bank.apply_feedback(
            incident_id=body.incident_id,
            action=body.action,
            edited_fix=body.edited_fix,
            engineer_feedback=body.engineer_feedback,
            engineer_name=body.engineer_name
        )
    return {"status": "feedback_retained", "hindsight_result": res}

class InvestigateRequestBody(BaseModel):
    incident_id: Optional[str] = None
    incident: Optional[Incident] = None
    interaction_number: int = 1

class SeedRequestBody(BaseModel):
    stage: int = 5
    bank_id: Optional[str] = "team-payments"

@app.get("/api/incidents")
def list_incidents():
    from backend.seed import load_incidents_from_file
    return load_incidents_from_file()

@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    from backend.seed import load_incidents_from_file
    incidents = load_incidents_from_file()
    inc = next((i for i in incidents if i.id == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc

@app.post("/api/seed")
async def seed_endpoint(body: SeedRequestBody):
    from backend.seed import aseed_stage
    await aseed_stage(stage=body.stage, bank_id=body.bank_id or settings.HINDSIGHT_BANK_ID)
    return {
        "status": "seeded",
        "stage": body.stage,
        "bank_id": body.bank_id or settings.HINDSIGHT_BANK_ID,
        "memories_count": hindsight.get_memories_count(settings.HINDSIGHT_BANK_ID)
    }

@app.post("/api/investigate")
@app.post("/api/incident-triage")
@app.post("/api/incident/triage")
def run_investigation(body: InvestigateRequestBody):
    from backend.agent.investigator import investigator
    from backend.seed import load_incidents_from_file
    
    target_incident = body.incident
    if not target_incident and body.incident_id:
        incidents = load_incidents_from_file()
        target_incident = next((i for i in incidents if i.id == body.incident_id), None)
        
    if not target_incident:
        raise HTTPException(status_code=400, detail="Either incident or incident_id must be provided")

    result = investigator.investigate(target_incident, interaction_number=body.interaction_number)
    return result

@app.post("/api/investigate/before-after")
def compare_before_after(body: InvestigateRequestBody):
    """
    Runs the SAME incident against:
    1. Before: Empty Memory Bank (Cold Start baseline)
    2. After: Current Trained Memory Bank
    Returns side-by-side comparison illustrating Hindsight value proposition.
    """
    from backend.agent.investigator import investigator
    from backend.seed import load_incidents_from_file
    
    target_incident = body.incident
    if not target_incident and body.incident_id:
        incidents = load_incidents_from_file()
        target_incident = next((i for i in incidents if i.id == body.incident_id), None)
        
    if not target_incident:
        raise HTTPException(status_code=400, detail="Incident not found")

    # Run "Before" (Cold Start: interaction 1 with empty memory simulation)
    before_result = investigator.investigate(target_incident, interaction_number=1)
    
    # Run "After" (Trained: uses current bank memories)
    after_result = investigator.investigate(target_incident, interaction_number=max(body.interaction_number, 5))

    return {
        "incident_id": target_incident.id,
        "before": before_result,
        "after": after_result,
        "improvement_highlights": [
            f"Confidence upgraded from {before_result.confidence} to {after_result.confidence}",
            f"Identified {len(after_result.retrieved_memories)} relevant past operational incidents vs 0 on cold start",
            f"Execution time: {after_result.execution_time_ms:.1f}ms with precision root cause hypothesis",
            f"Approval policy gate enforced: {after_result.recommendation.approval_required}"
        ]
    }

@app.get("/api/scoreboard")
def get_scoreboard():
    """
    Returns actual benchmark evaluation across interactions 1..20 on held-out simulated incidents.
    """
    from backend.evaluation import get_or_run_eval
    return get_or_run_eval()

# Serve production frontend build if dist folder exists
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "Frontend not found"}

