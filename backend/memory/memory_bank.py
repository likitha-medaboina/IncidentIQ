from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.memory.hindsight_adapter import hindsight
from backend.models import Incident, RetainPayload, LearnedPattern

class MemoryBankManager:
    """
    Orchestrates memory bank operations for a dedicated team (e.g. 'team-payments').
    Encapsulates retain, recall, reflect, and feedback/obsolescence tracking.
    """
    def __init__(self, bank_id: Optional[str] = None):
        self.bank_id = bank_id or settings.HINDSIGHT_BANK_ID

    def retain_incident(
        self,
        incident: Incident,
        fix_applied: Optional[str] = None,
        outcome: str = "worked",
        engineer_feedback: Optional[str] = None,
        engineer_name: str = "oncall-engineer"
    ) -> Dict[str, Any]:
        """
        Retain an incident record in Hindsight with structured log signature, symptoms, cause, and fix.
        """
        log_signature = "\n".join(incident.logs[:3]) if incident.logs else incident.alert_text
        deploy_info = ""
        if incident.deploy_events:
            d = incident.deploy_events[0]
            deploy_info = f"Commit: {d.commit_hash} by {d.author} ('{d.message}'), configs: {d.config_changes}"

        # Structured content format designed for Hindsight extraction & multi-strategy recall
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
            f"Resolved by: {engineer_name}"
        )

        metadata = {
            "incident_id": incident.id,
            "service": incident.service,
            "severity": incident.severity,
            "root_cause": incident.root_cause,
            "fix_applied": fix_applied or incident.recommended_fix,
            "outcome": outcome,
            "engineer_feedback": engineer_feedback or "",
            "engineer_name": engineer_name,
            "time_to_resolve_minutes": incident.time_to_resolve_minutes,
            "has_deploy_event": bool(incident.deploy_events),
            "config_changes": incident.deploy_events[0].config_changes if incident.deploy_events else {},
            "commit_hash": incident.deploy_events[0].commit_hash if incident.deploy_events else "",
            "kafka_lag": incident.metrics.kafka_lag,
            "memory_rss_bytes": incident.metrics.memory_rss_bytes,
            "memory_limit_bytes": incident.metrics.memory_limit_bytes,
            "connection_pool_active": incident.metrics.connection_pool_active,
            "connection_pool_max": incident.metrics.connection_pool_max,
            "is_simulated": True
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

        return hindsight.retain(
            bank_id=self.bank_id,
            content=content,
            metadata=metadata,
            tags=tags
        )

    def retain_policy(self, policy_id: str, title: str, rule: str, applies_to: List[str]) -> Dict[str, Any]:
        """
        Retain a team operational policy in Hindsight.
        """
        content = f"TEAM POLICY [{policy_id}]: {title}. Rule: {rule}. Applies to: {', '.join(applies_to)}."
        metadata = {
            "policy_id": policy_id,
            "title": title,
            "rule": rule,
            "applies_to": applies_to,
            "is_policy": True
        }
        return hindsight.retain(
            bank_id=self.bank_id,
            content=content,
            metadata=metadata,
            tags=["policy", "team-governance"]
        )

    def recall_for_alert(
        self,
        service: str,
        error_signature: str,
        deploy_info: Optional[str] = None,
        metrics_info: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query memory with service, error signature, deploy info, and metric signals.
        """
        query_parts = [service, error_signature]
        if deploy_info:
            query_parts.append(deploy_info)
        if metrics_info:
            query_parts.append(metrics_info)
        query = " ".join(query_parts)

        return hindsight.recall(
            bank_id=self.bank_id,
            query=query,
            service=service,
            top_k=top_k
        )

    def recall_obsolete(self, query: str, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recall obsolete incidents that match query terms, scored by weighted features.
        """
        return hindsight.recall_obsolete(
            bank_id=self.bank_id,
            query=query,
            service=service
        )

    def recall_failed_fixes(self, query: str = "", service: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recall incidents with failed fixes to surface in Memory Correction.
        """
        return hindsight.recall_failed_fixes(
            bank_id=self.bank_id,
            query=query,
            service=service
        )

    def reflect_patterns(self) -> List[LearnedPattern]:
        """
        Trigger Hindsight cross-incident reflection to synthesize Learned Patterns.
        """
        return hindsight.reflect(bank_id=self.bank_id)

    def mark_fix_obsolete(self, incident_id: str, reason: str, engineer_name: str = "oncall-engineer") -> Dict[str, Any]:
        """
        Marks a historical fix as obsolete so the agent stops recommending it and explains why.
        """
        content = f"OBSOLETE FIX NOTICE for Incident {incident_id}. Reason: {reason}. Marked by {engineer_name}."
        metadata = {
            "incident_id": incident_id,
            "outcome": "obsolete",
            "is_obsolete": True,
            "obsolete_reason": reason,
            "engineer_name": engineer_name,
            "engineer_feedback": f"Obsolete: {reason}"
        }
        return hindsight.retain(
            bank_id=self.bank_id,
            content=content,
            metadata=metadata,
            tags=["obsolete-fix", f"incident:{incident_id}"]
        )

    def apply_feedback(
        self,
        incident_id: str,
        action: str,  # accept, reject, edit
        edited_fix: Optional[str] = None,
        engineer_feedback: Optional[str] = None,
        engineer_name: str = "oncall-engineer"
    ) -> Dict[str, Any]:
        """
        Records human on-call feedback. Down-weights rejected fixes, cements accepted fixes.
        """
        outcome = "worked" if action in ("accept", "edit") else "failed"
        content = (
            f"FEEDBACK on Incident {incident_id} by {engineer_name}: "
            f"Action={action.upper()}, FixApplied='{edited_fix or 'Default'}', "
            f"Outcome={outcome}, Comments='{engineer_feedback or 'None'}'"
        )
        metadata = {
            "incident_id": incident_id,
            "outcome": outcome,
            "action": action,
            "fix_applied": edited_fix or "",
            "engineer_feedback": engineer_feedback or "",
            "engineer_name": engineer_name
        }
        return hindsight.retain(
            bank_id=self.bank_id,
            content=content,
            metadata=metadata,
            tags=["engineer-feedback", f"outcome:{outcome}"]
        )

# Team payments memory bank
payments_memory_bank = MemoryBankManager(bank_id="team-payments")
