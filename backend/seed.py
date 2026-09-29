import os
import json
import argparse
from typing import List, Dict, Any, Optional
from backend.models import Incident
from backend.memory.memory_bank import payments_memory_bank
from backend.memory.hindsight_adapter import hindsight
from backend.db.database import db

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_incidents.json")

def load_incidents_from_file() -> List[Incident]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Incident(**item) for item in data]

def init_bank_clean(bank_id: str = "team-payments"):
    """
    Initializes a completely empty memory bank for cold start.
    Stores policies separately; 0 incident memories.
    """
    hindsight.reset_bank(bank_id)
    payments_memory_bank.retain_policy(
        policy_id="POL-001",
        title="Prod Rollback Policy",
        rule="Automated production rollbacks require explicit human on-call engineer sign-off.",
        applies_to=["payment-service", "billing-worker"]
    )
    payments_memory_bank.retain_policy(
        policy_id="POL-002",
        title="Pod Memory Ceiling Gate",
        rule="Increasing pod memory limits beyond 1Gi requires secondary sign-off from Tech Lead.",
        applies_to=["payment-service"]
    )

def seed_historical_corpus(bank_id: str = "team-payments"):
    """
    Seeds baseline historical incidents ONCE at the start:
    Includes batch-size OOMs (INC-1002), Kafka lag incident (INC-1007),
    DB connection issues (INC-1004, INC-1009), and marks legacy G1GC fix (INC-1003) as obsolete.
    """
    all_incidents = load_incidents_from_file()
    # Exclude milestone test incidents to keep eval clean
    milestone_ids = {"INC-1001", "INC-1005", "INC-1012", "INC-1020"}
    historical = [i for i in all_incidents if i.id not in milestone_ids]

    print(f"\n[*] Seeding historical incident corpus into bank '{bank_id}' ({len(historical)} historical incidents)...")
    for inc in historical:
        db.save_incident(inc)
        payments_memory_bank.retain_incident(
            incident=inc,
            fix_applied=inc.recommended_fix,
            outcome=inc.outcome,
            engineer_feedback=f"Historical resolution: {inc.root_cause}",
            engineer_name=inc.engineer_name
        )

    # Mark legacy fix for INC-1003 as obsolete
    payments_memory_bank.mark_fix_obsolete(
        incident_id="INC-1003",
        reason="payment-service migrated to Java 21 ZGC; legacy G1GC tuning parameters are deprecated.",
        engineer_name="lead-architect"
    )

    # Reflect to synthesize initial patterns
    patterns = payments_memory_bank.reflect_patterns()
    print(f"[+] Historical seeding complete. Synthesized {len(patterns)} initial Learned Patterns.\n")

def seed_stage(stage: int = 5, bank_id: str = "team-payments"):
    """
    Seeds Hindsight memory bank to match the exact demo state for each stage:
    - Stage 0 / 1 (Cold Start): Clean bank with policies only (0 incident memories).
    - Stage 5 (Deploy OOM): Historical corpus + Interaction 1 (INC-1001 resolved).
      Held-out test milestones (INC-1005, INC-1012, INC-1020) are excluded.
      INC-1003 is marked OBSOLETE.
    - Stage 12 (Disambiguation): Stage 5 bank + cumulative Interaction 5 (INC-1005 resolved).
    - Stage 20 (Obsolete Fix): Stage 12 bank + cumulative Interaction 12 (INC-1012 resolved).
    """
    init_bank_clean(bank_id)
    if stage <= 1:
        # Cold start: strictly 0 incident memories per Issue 1
        return

    all_incidents = load_incidents_from_file()
    inc_map = {i.id: i for i in all_incidents}

    # Step 1: Retain cumulative Interaction 1 (INC-1001)
    inc1 = inc_map.get("INC-1001")
    if inc1:
        db.save_incident(inc1)
        payments_memory_bank.retain_incident(
            incident=inc1,
            fix_applied="Capture JVM thread and heap dumps from running container replica (payment-service)",
            outcome="worked",
            engineer_feedback="Resolved in 55m: Uncharacterized heap exhaustion during scheduled bulk batch ingestion.",
            engineer_name=inc1.engineer_name
        )

    # Step 2: Seed baseline historical corpus (excluding held-out milestone test incidents)
    milestone_ids = {"INC-1001", "INC-1005", "INC-1012", "INC-1020"}
    historical = [i for i in all_incidents if i.id not in milestone_ids]
    for inc in historical:
        db.save_incident(inc)
        payments_memory_bank.retain_incident(
            incident=inc,
            fix_applied=inc.recommended_fix,
            outcome=inc.outcome,
            engineer_feedback=f"Historical resolution: {inc.root_cause}",
            engineer_name=inc.engineer_name
        )

    # Mark legacy G1GC fix for INC-1003 as obsolete
    payments_memory_bank.mark_fix_obsolete(
        incident_id="INC-1003",
        reason="payment-service migrated to Java 21 ZGC; legacy G1GC tuning parameters are deprecated.",
        engineer_name="lead-architect"
    )

    # If stage >= 12: include cumulative outcome of Interaction 5 (INC-1005)
    if stage >= 12:
        inc5 = inc_map.get("INC-1005")
        if inc5:
            db.save_incident(inc5)
            payments_memory_bank.retain_incident(
                incident=inc5,
                fix_applied="Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500)",
                outcome="worked",
                engineer_feedback="Interaction 5 resolved: Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500).",
                engineer_name=inc5.engineer_name
            )

    # If stage >= 20: include cumulative outcome of Interaction 12 (INC-1012)
    if stage >= 20:
        inc12 = inc_map.get("INC-1012")
        if inc12:
            db.save_incident(inc12)
            payments_memory_bank.retain_incident(
                incident=inc12,
                fix_applied="Scale payment-service HorizontalPodAutoscaler minReplicas from 2 to 6",
                outcome="worked",
                engineer_feedback="Interaction 12 resolved: Scale payment-service HorizontalPodAutoscaler minReplicas from 2 to 6.",
                engineer_name=inc12.engineer_name
            )

    payments_memory_bank.reflect_patterns()

def format_incident_for_retention(
    incident: Incident,
    fix_applied: Optional[str] = None,
    outcome: str = "worked",
    engineer_feedback: Optional[str] = None,
    engineer_name: Optional[str] = None,
    is_obsolete: bool = False,
    obsolete_reason: str = ""
) -> Dict[str, Any]:
    log_signature = "\n".join(incident.logs[:3]) if incident.logs else incident.alert_text
    deploy_info = ""
    if incident.deploy_events:
        d = incident.deploy_events[0]
        deploy_info = f"Commit: {d.commit_hash} by {d.author} ('{d.message}'), configs: {d.config_changes}"

    content = (
        f"Service: {incident.service} | Severity: {incident.severity}\n"
        f"Alert: {incident.alert_text}\n"
        f"Log Signature: {log_signature}\n"
        f"Metrics: RSS={incident.metrics.memory_rss_bytes // (1024*1024)}MB/{incident.metrics.memory_limit_bytes // (1024*1024)}MB, CPU={incident.metrics.cpu_percent}%, KafkaLag={incident.metrics.kafka_lag}\n"
        f"Deploy Info: {deploy_info}\n"
        f"Suspected Root Cause: {incident.root_cause}\n"
        f"Fix Applied: {fix_applied or incident.recommended_fix}\n"
        f"Outcome: {outcome}\n"
        f"Engineer Feedback: {engineer_feedback or 'None'}\n"
        f"Resolved by: {engineer_name or incident.engineer_name}"
    )

    metadata = {
        "incident_id": incident.id,
        "service": incident.service,
        "severity": incident.severity,
        "root_cause": incident.root_cause,
        "fix_applied": fix_applied or incident.recommended_fix,
        "outcome": outcome,
        "engineer_feedback": engineer_feedback or "",
        "engineer_name": engineer_name or incident.engineer_name,
        "time_to_resolve_minutes": str(incident.time_to_resolve_minutes),
        "has_deploy_event": str(bool(incident.deploy_events)),
        "config_changes": str(incident.deploy_events[0].config_changes if incident.deploy_events else {}),
        "commit_hash": str(incident.deploy_events[0].commit_hash if incident.deploy_events else ""),
        "kafka_lag": str(incident.metrics.kafka_lag),
        "memory_rss_bytes": str(incident.metrics.memory_rss_bytes),
        "memory_limit_bytes": str(incident.metrics.memory_limit_bytes),
        "connection_pool_active": str(incident.metrics.connection_pool_active),
        "connection_pool_max": str(incident.metrics.connection_pool_max),
        "is_simulated": "True",
        "is_obsolete": str(is_obsolete),
        "obsolete_reason": obsolete_reason
    }

    tags = [
        f"service:{incident.service}",
        f"severity:{incident.severity}",
        f"outcome:{outcome}",
        "simulated"
    ]
    if "oomkilled" in incident.alert_text.lower() or any("137" in l for l in incident.logs):
        tags.append("oomkilled")
    if "hikaripool" in incident.alert_text.lower() or any("hikari" in l.lower() for l in incident.logs):
        tags.append("db-connection-pool")
    if incident.deploy_events:
        tags.append("recent-deploy")

    return {
        "content": content,
        "metadata": metadata,
        "tags": tags
    }

def build_seed_items(stage: int = 5) -> List[Dict[str, Any]]:
    """
    Builds the batch of memory items for a given stage to be retained via aretain_batch.
    """
    if stage <= 1:
        return []

    all_incidents = load_incidents_from_file()
    inc_map = {i.id: i for i in all_incidents}
    items: List[Dict[str, Any]] = []

    # Step 1: Retain cumulative Interaction 1 (INC-1001)
    inc1 = inc_map.get("INC-1001")
    if inc1:
        db.save_incident(inc1)
        items.append(format_incident_for_retention(
            incident=inc1,
            fix_applied="Capture JVM thread and heap dumps from running container replica (payment-service)",
            outcome="worked",
            engineer_feedback="Resolved in 55m: Uncharacterized heap exhaustion during scheduled bulk batch ingestion.",
            engineer_name=inc1.engineer_name
        ))

    # Step 2: Historical baseline corpus (excluding held-out milestone test incidents)
    milestone_ids = {"INC-1001", "INC-1005", "INC-1012", "INC-1020"}
    historical = [i for i in all_incidents if i.id not in milestone_ids]
    for inc in historical:
        db.save_incident(inc)
        is_obs = (inc.id == "INC-1003")
        obs_reason = "payment-service migrated to Java 21 ZGC; legacy G1GC tuning parameters are deprecated." if is_obs else ""
        items.append(format_incident_for_retention(
            incident=inc,
            fix_applied=inc.recommended_fix,
            outcome=inc.outcome,
            engineer_feedback=f"Historical resolution: {inc.root_cause}",
            engineer_name=inc.engineer_name,
            is_obsolete=is_obs,
            obsolete_reason=obs_reason
        ))

    # If stage >= 12: include cumulative outcome of Interaction 5 (INC-1005)
    if stage >= 12:
        inc5 = inc_map.get("INC-1005")
        if inc5:
            db.save_incident(inc5)
            items.append(format_incident_for_retention(
                incident=inc5,
                fix_applied="Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500)",
                outcome="worked",
                engineer_feedback="Interaction 5 resolved: Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500).",
                engineer_name=inc5.engineer_name
            ))

    # If stage >= 20: include cumulative outcome of Interaction 12 (INC-1012)
    if stage >= 20:
        inc12 = inc_map.get("INC-1012")
        if inc12:
            db.save_incident(inc12)
            items.append(format_incident_for_retention(
                incident=inc12,
                fix_applied="Scale payment-service HorizontalPodAutoscaler minReplicas from 2 to 6",
                outcome="worked",
                engineer_feedback="Interaction 12 resolved: Scale payment-service HorizontalPodAutoscaler minReplicas from 2 to 6.",
                engineer_name=inc12.engineer_name
            ))

    return items

async def aseed_stage(stage: int = 5, bank_id: str = "team-payments"):
    """
    Asynchronously seeds Hindsight memory bank using aretain_batch to avoid
    nested event loop conflicts during FastAPI/uvicorn startup.
    """
    init_bank_clean(bank_id)
    if stage <= 1:
        return

    items = build_seed_items(stage)
    if items:
        await hindsight.aretain_batch(bank_id=bank_id, items=items)
    payments_memory_bank.reflect_patterns()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed IncidentIQ Hindsight Memory Bank")
    parser.add_argument("--stage", type=int, default=5, help="Seed stage: 0, 1, 5, 12, or 20")
    parser.add_argument("--bank", type=str, default="team-payments", help="Hindsight memory bank ID")
    args = parser.parse_args()
    seed_stage(stage=args.stage, bank_id=args.bank)
