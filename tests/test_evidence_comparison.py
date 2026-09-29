import pytest
from backend.models import Incident, MetricsSnapshot, DeployEvent
from backend.agent.investigator import AgentInvestigator

@pytest.fixture
def sample_incident():
    return Incident(
        id="INC-LIVE-001",
        timestamp="2026-09-28T10:00:00Z",
        service="payment-service",
        severity="P1-CRITICAL",
        alert_text="PaymentServiceOOMKilled - Pod memory limit exceeded (511Mi/512Mi)",
        logs=[
            "java.lang.OutOfMemoryError: Java heap space",
            "Container killed: exit code 137 (OOMKilled)"
        ],
        metrics=MetricsSnapshot(
            memory_rss_bytes=511 * 1024 * 1024,
            memory_limit_bytes=512 * 1024 * 1024,
            cpu_percent=88.5,
            kafka_lag=48213,
            p99_latency_ms=1420.0
        ),
        deploy_events=[],  # No deploy! Live is traffic surge!
        root_cause="Consumer backlog queue spike",
        recommended_fix="Scale replicas and absorb burst",
        engineer_name="oncall-devops"
    )

def test_evidence_comparison_detects_differing_deploy_signals(sample_incident):
    agent = AgentInvestigator()

    recalled_item = {
        "id": "INC-HIST-004",
        "text": "Service: payment-service | Alert: OOMKilled | Deploy: commit abcd12 PAYMENT_BATCH_SIZE=5000 | Fix: rollback batch size to 500",
        "score": 0.88,
        "is_obsolete": False,
        "metadata": {
            "has_deploy_event": True,
            "fix_applied": "Rollback PAYMENT_BATCH_SIZE to 500",
            "outcome": "worked"
        }
    }

    comp = agent.compare_evidence(sample_incident, recalled_item)

    # 1. Must identify matching log signals
    assert any("exit code 137" in s or "OOMKilled" in s for s in comp.matching_signals)

    # 2. Must identify differing deployment context (crucial guardrail!)
    assert any("deploy" in s.lower() for s in comp.differing_signals)

    # 3. Must warn if differing signals indicate traffic surge vs deploy
    assert comp.guardrail_warning is not None or any("traffic" in s.lower() or "deploy" in s.lower() for s in comp.differing_signals)

def test_evidence_comparison_flags_obsolete_fix(sample_incident):
    agent = AgentInvestigator()

    recalled_item = {
        "id": "INC-HIST-002",
        "text": "Service: payment-service | Alert: OOMKilled | Fix: Tune G1GC parameters",
        "score": 0.75,
        "is_obsolete": True,
        "obsolete_reason": "payment-service migrated to Java 21 ZGC",
        "metadata": {
            "fix_applied": "Set -XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=45",
            "outcome": "obsolete"
        }
    }

    comp = agent.compare_evidence(sample_incident, recalled_item)
    assert comp.is_obsolete is True
    assert "OBSOLETE" in (comp.guardrail_warning or "")
    assert "Java 21 ZGC" in (comp.obsolete_reason or "")

def test_investigator_surfaces_failed_fix_in_memory_correction(sample_incident):
    from backend.memory.hindsight_adapter import hindsight
    hindsight.retain(
        bank_id="team-payments",
        content="Service: payment-service | Alert: OOMKilled | Deploy: PAYMENT_BATCH_SIZE=4000 | Fix: rollback batch size to 500",
        metadata={
            "incident_id": "INC-TEST-ACTIVE",
            "service": "payment-service",
            "outcome": "resolved",
            "has_deploy_event": True,
            "config_changes": {"PAYMENT_BATCH_SIZE": 4000},
            "fix_applied": "Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500)"
        },
        tags=["payment-service", "oomkilled", "recent-deploy"]
    )
    hindsight.retain(
        bank_id="team-payments",
        content="Service: payment-service | Alert: OOMKilled | Attempt: restart pods failed",
        metadata={
            "incident_id": "INC-TEST-FAIL",
            "service": "payment-service",
            "outcome": "failed",
            "fix_applied": "Simple pod restart without config rollback",
            "root_cause": "Pod restart without config rollback failed; pod crashed in 3 mins."
        },
        tags=["payment-service", "oomkilled", "rejected-fix"]
    )
    agent = AgentInvestigator()
    # Mock incident with deploy
    sample_incident.deploy_events = [
        DeployEvent(
            commit_hash="c7104b2",
            author="mike-dev",
            message="bump batch",
            timestamp="2026-09-28T09:00:00Z",
            config_changes={"PAYMENT_BATCH_SIZE": 5000}
        )
    ]
    res = agent.investigate(sample_incident, interaction_number=20)
    
    # 1. Active ranked memories must NOT include failed-outcome incidents
    for m in res.retrieved_memories:
        assert m.get("outcome") != "failed", f"Failed incident {m['id']} should not be in active ranked list"
    
    # 2. Failed incidents must appear in Memory Correction list alongside obsolete ones
    failed_in_correction = [m for m in res.obsolete_memories if m.get("outcome") == "failed" or m.get("is_failed_fix")]
    assert len(failed_in_correction) > 0, "Expected failed-outcome memories in Memory Correction list"
    assert any("FAILED" in m["why_matched"] for m in failed_in_correction)

    # 3. Failed fix must be explicitly cited in contradicting evidence
    assert any("FAILED" in ev or "failed" in ev.lower() for ev in res.contradicting_evidence)
