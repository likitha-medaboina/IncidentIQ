import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*StarletteDeprecationWarning.*")
warnings.filterwarnings("ignore", message=".*Using `httpx` with `starlette.testclient` is deprecated.*")

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.evaluation import get_or_run_eval, assert_held_out_excluded, HELD_OUT_INCIDENT_IDS
from backend.memory.hindsight_adapter import hindsight

def test_get_or_run_eval_and_scoreboard_api():
    # 1. Direct call to get_or_run_eval()
    eval_data = get_or_run_eval()
    assert isinstance(eval_data, dict)
    assert "interactions" in eval_data
    assert "summary" in eval_data

    interactions = eval_data["interactions"]
    assert len(interactions) >= 15, f"Expected at least 15 evaluated interactions, got {len(interactions)}"

    # Assert real numbers in interaction metrics
    first_int = interactions[0]
    assert 0.0 <= first_int["root_cause_accuracy"] <= 1.0
    assert first_int["steps_count"] > 0
    assert first_int["recall_ms"] >= 0.0

    last_int = interactions[-1]
    assert 0.0 <= last_int["root_cause_accuracy"] <= 1.0
    assert last_int["steps_count"] > 0
    # Accuracy should improve from first to last
    assert last_int["root_cause_accuracy"] >= first_int["root_cause_accuracy"]

    summary = eval_data["summary"]
    assert "root_cause_accuracy_growth" in summary
    assert "avg_investigation_steps" in summary
    assert "recommendation_acceptance_rate" in summary
    assert "mean_recall_latency_ms" in summary
    assert "hindsight_mode" in summary
    assert summary["hindsight_mode"] in ("Hindsight: LIVE", "Hindsight: FALLBACK")

    # 2. HTTP GET /api/scoreboard via TestClient
    client = TestClient(app)
    response = client.get("/api/scoreboard")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "interactions" in data
    assert "summary" in data
    assert len(data["interactions"]) >= 15
    assert "%" in data["summary"]["root_cause_accuracy_growth"]
    assert "steps" in data["summary"]["avg_investigation_steps"]
    assert "hindsight_mode" in data["summary"]

def test_held_out_incidents_excluded_and_failure_on_leak():
    """
    Requirement 3: Asserts held-out incidents are excluded from the bank when evaluated.
    Fails if a held-out ID appears in recall results.
    """
    test_bank = "test-held-out-integrity"
    hindsight.reset_bank(test_bank)

    # 1. Normal clean state: all held-out incident IDs pass exclusion checks
    for hid in HELD_OUT_INCIDENT_IDS:
        assert_held_out_excluded(test_bank, hid)
        assert_held_out_excluded(test_bank, hid, [{"id": "INC-1002", "score": 0.88}])

    # 2. Fails (raises AssertionError) if a held-out ID appears in recall results
    with pytest.raises(AssertionError, match="appeared in recall results"):
        assert_held_out_excluded(
            bank_id=test_bank,
            target_incident_id="INC-1005",
            recalled_memories=[
                {"id": "INC-1002", "score": 0.85},
                {"id": "INC-1005", "score": 0.98}  # Contamination leak
            ]
        )

    # 3. Fails (raises AssertionError) if a held-out ID is present in the memory bank prior to evaluation
    hindsight.embedded.retain(
        bank_id=test_bank,
        content="Contaminated bank entry with held-out incident",
        metadata={"incident_id": "INC-1020"}
    )
    with pytest.raises(AssertionError, match="was found in memory bank"):
        assert_held_out_excluded(
            bank_id=test_bank,
            target_incident_id="INC-1020"
        )
