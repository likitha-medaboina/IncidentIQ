import pytest
from backend.memory.hindsight_adapter import HindsightAdapter
from backend.memory.memory_bank import MemoryBankManager
from backend.models import Incident, MetricsSnapshot, DeployEvent

def test_hindsight_retain_and_recall():
    adapter = HindsightAdapter()
    bank_id = "test-team-payments"
    adapter.reset_bank(bank_id)

    # 1. Retain incident
    res = adapter.retain(
        bank_id=bank_id,
        content="Service: payment-service | Alert: OOMKilled exit code 137 | Cause: batch size too large | Fix: rollback batch size to 500",
        metadata={"incident_id": "INC-TEST-1", "outcome": "worked"},
        tags=["payment-service", "oomkilled"]
    )
    assert res["status"] in ("retained", "updated")

    # 2. Recall matching incident
    matches = adapter.recall(
        bank_id=bank_id,
        query="payment-service OOMKilled exit code 137",
        service="payment-service"
    )
    assert len(matches) > 0
    top = matches[0]
    assert top["id"] == "INC-TEST-1"
    assert top["score"] > 0.3
    assert "OOMKilled" in top["why_matched"]

def test_hindsight_downweights_failed_fixes():
    adapter = HindsightAdapter()
    bank_id = "test-team-payments-downweight"
    adapter.reset_bank(bank_id)

    # Retain successful incident
    adapter.retain(
        bank_id=bank_id,
        content="Incident A: payment-service OOMKilled. Fix: rollback batch size worked flawlessly.",
        metadata={"incident_id": "INC-A", "outcome": "worked"},
        tags=["oomkilled"]
    )

    # Retain failed incident
    adapter.retain(
        bank_id=bank_id,
        content="Incident B: payment-service OOMKilled. Fix: pod restart failed immediately.",
        metadata={"incident_id": "INC-B", "outcome": "failed"},
        tags=["oomkilled"]
    )

    matches = adapter.recall(bank_id=bank_id, query="payment-service OOMKilled")
    assert len(matches) == 2
    # Successful fix must score higher than failed fix
    assert matches[0]["id"] == "INC-A"
    assert matches[0]["score"] > matches[1]["score"]

def test_hindsight_obsolete_fix():
    adapter = HindsightAdapter()
    bank_id = "test-team-payments-obsolete"
    adapter.reset_bank(bank_id)

    adapter.retain(
        bank_id=bank_id,
        content="Legacy fix: tune G1GC parameters for payment-service OOM",
        metadata={"incident_id": "INC-LEGACY", "outcome": "worked"},
        tags=["oomkilled"]
    )

    # Mark as obsolete
    adapter.retain(
        bank_id=bank_id,
        content="Legacy fix: tune G1GC parameters for payment-service OOM",
        metadata={
            "incident_id": "INC-LEGACY",
            "outcome": "obsolete",
            "is_obsolete": True,
            "obsolete_reason": "payment-service migrated to Java 21 ZGC"
        }
    )

    matches = adapter.recall(bank_id=bank_id, query="payment-service OOM G1GC")
    assert len(matches) > 0
    assert matches[0]["is_obsolete"] is True
    assert "Java 21 ZGC" in matches[0]["obsolete_reason"]

def test_hindsight_reflect():
    adapter = HindsightAdapter()
    bank_id = "test-team-payments-reflect"
    adapter.reset_bank(bank_id)

    # Retain multiple batch OOM incidents
    adapter.retain(
        bank_id=bank_id,
        content="Incident 1: payment-service OOMKilled exit code 137 after batch size increased to 5000",
        metadata={"incident_id": "INC-1", "outcome": "worked"}
    )
    adapter.retain(
        bank_id=bank_id,
        content="Incident 2: payment-service OOMKilled exit code 137 after batch size bumped to 8000",
        metadata={"incident_id": "INC-2", "outcome": "worked"}
    )

    patterns = adapter.reflect(bank_id=bank_id)
    assert len(patterns) >= 1
    assert "batch" in patterns[0].pattern.lower()
    assert patterns[0].confidence in ("MEDIUM", "HIGH")
