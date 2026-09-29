from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class DeployEvent(BaseModel):
    commit_hash: str
    author: str
    message: str
    timestamp: str
    config_changes: Dict[str, Any] = Field(default_factory=dict)

class MetricsSnapshot(BaseModel):
    memory_rss_bytes: int
    memory_limit_bytes: int
    cpu_percent: float
    kafka_lag: int = 0
    p99_latency_ms: float
    gc_pause_ms: float = 0.0
    active_threads: int = 0
    connection_pool_active: int = 0
    connection_pool_max: int = 0

class Incident(BaseModel):
    id: str
    timestamp: str
    service: str
    severity: Literal["P1-CRITICAL", "P2-HIGH", "P3-MEDIUM", "P4-LOW"]
    alert_text: str
    logs: List[str]
    metrics: MetricsSnapshot
    deploy_events: List[DeployEvent] = Field(default_factory=list)
    root_cause: str
    recommended_fix: str
    time_to_resolve_minutes: int = 15
    engineer_name: str = "oncall-devops"
    outcome: Literal["resolved", "failed", "obsolete"] = "resolved"
    is_simulated: bool = True
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None

class EvidenceComparison(BaseModel):
    recalled_incident_id: str
    recalled_summary: str
    match_score: float
    matching_signals: List[str]
    differing_signals: List[str]
    past_fix_applied: str
    past_outcome: str
    is_obsolete: bool = False
    obsolete_reason: Optional[str] = None
    guardrail_warning: Optional[str] = None

class Recommendation(BaseModel):
    hypothesis: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    proposed_steps: List[str]
    source_memory_ids: List[str]
    approval_required: bool = False
    approval_policy_reason: Optional[str] = None
    action_type: str = "general_fix"  # e.g. "rollback_deploy", "tune_batch_size", "scale_workers"
    config_diff: Optional[Dict[str, Any]] = None
    obsolete_warning: Optional[str] = None

class RetainPayload(BaseModel):
    incident_id: str
    summary: str
    symptoms: str
    log_signature: str
    suspected_cause: str
    fix_applied: str
    outcome: Literal["worked", "failed", "obsolete"]
    engineer_feedback: Optional[str] = None
    engineer_name: str = "oncall-engineer"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_policy: bool = False

class FeedbackRequest(BaseModel):
    incident_id: str
    action: Literal["accept", "reject", "edit"]
    edited_fix: Optional[str] = None
    engineer_feedback: Optional[str] = None
    mark_as_obsolete: bool = False
    obsolete_reason: Optional[str] = None
    engineer_name: str = "oncall-engineer"

class LearnedPattern(BaseModel):
    id: str
    pattern: str
    evidence_incident_ids: List[str]
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    discovered_at: str
    recommendation: str

class MemoryTimelineEvent(BaseModel):
    id: str
    timestamp: str
    operation: Literal["RETAIN", "RECALL", "REFLECT", "POLICY"]
    bank_id: str
    query_or_summary: str
    matched_ids: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)

class InvestigationResult(BaseModel):
    incident: Incident
    hypothesis: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    proposed_steps: List[str]
    comparisons: List[EvidenceComparison]
    retrieved_memories: List[Dict[str, Any]]
    applied_policies: List[str]
    recommendation: Recommendation
    execution_time_ms: float
    interaction_number: int = 1
    obsolete_memories: List[Dict[str, Any]] = Field(default_factory=list)

class ScoreboardMetric(BaseModel):
    interaction: int
    incident_id: str
    root_cause_accuracy: float  # 0.0 to 1.0
    investigation_steps_count: int
    acceptance_status: str  # accepted, rejected, edited
    time_to_recall_ms: float
    confidence: str
    matched_past_incident: bool
    notes: str
