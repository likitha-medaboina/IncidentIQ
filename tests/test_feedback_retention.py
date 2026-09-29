import pytest
from backend.models import Incident, MetricsSnapshot, FeedbackRequest
from backend.memory.memory_bank import MemoryBankManager

def test_feedback_retention_and_downweighting():
    bank = MemoryBankManager(bank_id="test-team-feedback")
    bank.retain_incident(
        incident=Incident(
            id="INC-FB-101",
            timestamp="2026-09-28T12:00:00Z",
            service="payment-service",
            severity="P1-CRITICAL",
            alert_text="PaymentServiceOOMKilled exit code 137",
            logs=["exit code 137"],
            metrics=MetricsSnapshot(memory_rss_bytes=511*1024*1024, memory_limit_bytes=512*1024*1024, cpu_percent=75, p99_latency_ms=800),
            root_cause="Batch size too high",
            recommended_fix="Restart pod without config rollback",
            engineer_name="tester"
        ),
        fix_applied="Restart pod without config rollback",
        outcome="worked"
    )

    # Initially recalled with high score
    initial_matches = bank.recall_for_alert("payment-service", "PaymentServiceOOMKilled exit code 137")
    assert len(initial_matches) > 0
    initial_score = initial_matches[0]["score"]

    # Engineer rejects this fix because pod immediately crashed again!
    bank.apply_feedback(
        incident_id="INC-FB-101",
        action="reject",
        engineer_feedback="Restarting pod without config rollback failed; pod crashed again after 4 minutes.",
        engineer_name="sarah-oncall"
    )

    # Recall again - the rejected fix must be down-weighted!
    after_matches = bank.recall_for_alert("payment-service", "PaymentServiceOOMKilled exit code 137")
    assert len(after_matches) > 0
    assert after_matches[0]["outcome"] == "failed"
    assert after_matches[0]["score"] < initial_score
    assert "crashed again" in after_matches[0]["engineer_feedback"]

def test_marking_fix_obsolete_retention():
    bank = MemoryBankManager(bank_id="test-team-obsolete-feedback")
    bank.retain_incident(
        incident=Incident(
            id="INC-OBS-202",
            timestamp="2026-09-28T12:00:00Z",
            service="payment-service",
            severity="P2-HIGH",
            alert_text="Heap exhaustion GC pause",
            logs=["GC overhead limit exceeded"],
            metrics=MetricsSnapshot(memory_rss_bytes=480*1024*1024, memory_limit_bytes=512*1024*1024, cpu_percent=60, p99_latency_ms=900),
            root_cause="G1GC pause times",
            recommended_fix="Set -XX:MaxGCPauseMillis=200",
            engineer_name="tester"
        ),
        fix_applied="Set -XX:MaxGCPauseMillis=200",
        outcome="worked"
    )

    # Mark as obsolete after Java 21 migration
    bank.mark_fix_obsolete(
        incident_id="INC-OBS-202",
        reason="Obsolete after Java 21 ZGC migration; flag no longer supported.",
        engineer_name="lead-devops"
    )

    recalled = bank.recall_for_alert("payment-service", "Heap exhaustion GC pause")
    assert len(recalled) > 0
    assert recalled[0]["is_obsolete"] is True
    assert "Java 21 ZGC" in recalled[0]["obsolete_reason"]
