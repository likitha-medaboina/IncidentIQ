import sys
import uuid
import time
import threading
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests
import subprocess

app = FastAPI(title="Hindsight Memory Server", version="0.10.1")

# Reference the shared high-fidelity memory engine from hindsight singleton
from backend.memory.hindsight_adapter import hindsight
server_engine = hindsight.embedded

@app.get("/health")
@app.get("/api/v1/health")
def health():
    return {"status": "healthy", "service": "hindsight-memory-server"}

@app.get("/version")
def version():
    return {
        "api_version": "0.10.1",
        "features": {
            "observations": True,
            "mcp": True,
            "worker": True,
            "bank_config_api": True,
            "bank_llm_health": True,
            "file_upload_api": True,
            "document_export_api": True,
            "document_import_api": True,
            "audit_log": True,
            "llm_trace": True,
            "store_document_text": True
        }
    }

@app.post("/v1/default/banks/{bank_id}/memories")
async def retain_memories(bank_id: str, request: Request):
    data = await request.json()
    items = data.get("items", [])
    for item in items:
        content = item.get("content", "")
        metadata = item.get("metadata", {}) or {}
        tags = item.get("tags", []) or []
        doc_type = item.get("type", "experience")
        server_engine.retain(bank_id=bank_id, content=content, metadata=metadata, tags=tags, doc_type=doc_type)
    return {
        "success": True,
        "bank_id": bank_id,
        "items_count": len(items),
        "async": False,
        "operation_id": None,
        "operation_ids": None,
        "usage": None
    }

@app.post("/v1/default/banks/{bank_id}/memories/recall")
async def recall_memories(bank_id: str, request: Request):
    data = await request.json()
    query = data.get("query", "")
    recalled = server_engine.recall(bank_id=bank_id, query=query, top_k=10)
    results = []
    import json
    for m in recalled:
        meta = {
            **(m.get("metadata", {}) or {}),
            "why_matched": m.get("why_matched", ""),
            "feature_scores": json.dumps(m.get("feature_scores", {})),
            "is_obsolete": str(m.get("is_obsolete", False)),
            "obsolete_reason": m.get("obsolete_reason", ""),
            "outcome": m.get("outcome", "worked"),
            "engineer_feedback": m.get("engineer_feedback", "")
        }
        results.append({
            "id": m["id"],
            "text": m["text"],
            "type": m.get("type", "experience"),
            "entities": None,
            "context": None,
            "occurred_start": None,
            "occurred_end": None,
            "mentioned_at": None,
            "document_id": None,
            "metadata": meta,
            "chunk_id": None,
            "tags": m.get("tags", []),
            "source_fact_ids": None,
            "scores": {"final": m.get("score", 0.85)},
            "attachments": None
        })
    return {
        "results": results,
        "trace": None,
        "entities": None,
        "chunks": None,
        "source_facts": None,
        "source_facts_truncated": None
    }

@app.post("/v1/default/banks/{bank_id}/reflect")
async def reflect_memories(bank_id: str, request: Request):
    data = await request.json()
    query = data.get("query", "")
    patterns = server_engine.reflect(bank_id=bank_id, query=query)
    return {
        "facts": [{"id": p.id, "text": p.pattern, "confidence": p.confidence} for p in patterns],
        "trace": None
    }

@app.delete("/v1/default/banks/{bank_id}/memories")
def clear_memories(bank_id: str):
    server_engine.reset_bank(bank_id)
    return {"status": "cleared", "bank_id": bank_id}

@app.get("/v1/default/banks/{bank_id}/memories")
def list_memories(bank_id: str):
    mems = server_engine.banks.get(bank_id, [])
    return {"items": [{"id": m.id, "content": m.content, "metadata": m.metadata} for m in mems]}

_server_proc: Optional[subprocess.Popen] = None

def ensure_server_running(port: int = 8888, host: str = "127.0.0.1", wait_seconds: float = 4.0) -> bool:
    """
    Ensures that a Hindsight API server is active on the given port.
    If not already running, spawns an independent daemon subprocess with uvicorn.
    """
    global _server_proc
    try:
        r = requests.get(f"http://{host}:{port}/health", timeout=0.5)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    import subprocess
    import os
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cmd = [sys.executable, "-m", "backend.memory.hindsight_server"]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    sub_env = os.environ.copy()
    sub_env["PYTHONPATH"] = project_dir

    _server_proc = subprocess.Popen(
        cmd,
        cwd=project_dir,
        env=sub_env,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            r = requests.get(f"http://{host}:{port}/health", timeout=0.3)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.15)
    return False

def start_server(port: int = 8888, host: str = "127.0.0.1"):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start_server()
