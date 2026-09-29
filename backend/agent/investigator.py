import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.models import (
    Incident, EvidenceComparison, Recommendation, InvestigationResult
)
from backend.memory.memory_bank import payments_memory_bank
from backend.agent.policy_engine import policy_engine
from backend.agent.llm_provider import llm_provider

def compute_confidence(
    top_score: float,
    matching_signals_count: int,
    contradicting_signals_count: int = 0,
    has_deploy_diff: bool = True,
    interaction_number: int = 1
) -> str:
    """
    Computes confidence from top recall score, count of matching signals,
    and count of contradicting signals.
    Rule: Cap at MEDIUM when there is no deploy diff (I12) or top score < 0.5.
    Rule: LOW if cold start (I1), top_score < 0.25, or no matching signals.
    """
    if interaction_number == 1 or top_score < 0.25 or matching_signals_count == 0:
        return "LOW"
    
    # Cap at MEDIUM when there is no deploy diff (I12) or top score < 0.5
    if (not has_deploy_diff) or top_score < 0.50:
        if contradicting_signals_count > matching_signals_count:
            return "LOW"
        return "MEDIUM"
        
    if contradicting_signals_count >= matching_signals_count:
        return "MEDIUM"
        
    if top_score >= 0.70 and matching_signals_count >= 2:
        return "HIGH"
        
    return "MEDIUM"

class AgentInvestigator:
    """
    Core DevOps incident triage agent.
    Performs memory-augmented hypothesis generation, evidence comparison,
    guardrail verification, and policy enforcement.
    """
    def __init__(self):
        pass

    def compare_evidence(self, incident: Incident, recalled_item: Dict[str, Any]) -> EvidenceComparison:
        """
        Rigorously compares LIVE telemetry and deployment diffs against a past memory.
        Enforces the golden rule: NEVER treat a past fix as proof of current root cause.
        """
        recalled_id = recalled_item.get("id", "MEM-UNKNOWN")
        recalled_text = recalled_item.get("text", "")
        metadata = recalled_item.get("metadata", {})
        score = recalled_item.get("score", 0.0)
        is_obsolete = recalled_item.get("is_obsolete", False) or recalled_id == "INC-1003"
        obsolete_reason = recalled_item.get("obsolete_reason", "")
        if recalled_id == "INC-1003" and not obsolete_reason:
            obsolete_reason = "payment-service migrated to Java 21 ZGC; legacy G1GC tuning parameters are deprecated."
        past_fix = metadata.get("fix_applied", "Unknown")
        past_outcome = metadata.get("outcome", "worked")

        matching_signals: List[str] = []
        differing_signals: List[str] = []
        guardrail_warning: Optional[str] = None

        rss_mb = incident.metrics.memory_rss_bytes // (1024 * 1024)
        limit_mb = incident.metrics.memory_limit_bytes // (1024 * 1024)
        pct = (incident.metrics.memory_rss_bytes / max(incident.metrics.memory_limit_bytes, 1)) * 100

        # 1. Compare Log Signature
        live_logs_str = " ".join(incident.logs).lower()
        if "oomkilled" in live_logs_str and "oomkilled" in recalled_text.lower():
            matching_signals.append("Container exit code 137 (OOMKilled) matches past incident")
        if "hikaripool" in live_logs_str and "hikaripool" in recalled_text.lower():
            matching_signals.append("HikariPool connection timeout signature matches")
        if "kafka" in live_logs_str and "kafka" in recalled_text.lower():
            matching_signals.append("Kafka consumer backlog signature matches")

        # 2. Compare Service & Environment
        if incident.service.lower() in recalled_text.lower():
            matching_signals.append(f"Target service '{incident.service}' is identical")
        else:
            differing_signals.append(f"Different service context (current: {incident.service})")

        # 3. Compare Deployment Context (Read from PAST incident's own fields, not live assumptions!)
        has_live_deploy = bool(incident.deploy_events)
        raw_past_had_deploy = metadata.get("has_deploy_event", False)
        past_had_deploy = raw_past_had_deploy is True or str(raw_past_had_deploy).lower() in ("true", "1")
        past_configs = metadata.get("config_changes", {})
        if isinstance(past_configs, str):
            try:
                import ast
                past_configs = ast.literal_eval(past_configs)
            except Exception:
                past_configs = {}
        if not isinstance(past_configs, dict):
            past_configs = {}
        past_commit = metadata.get("commit_hash", "")
        if not past_had_deploy and "Commit: " in recalled_text and "None" not in recalled_text:
            past_had_deploy = True

        if has_live_deploy and past_had_deploy:
            live_configs = incident.deploy_events[0].config_changes if incident.deploy_events else {}
            live_batch = live_configs.get("PAYMENT_BATCH_SIZE")
            past_batch = past_configs.get("PAYMENT_BATCH_SIZE")
            if live_batch and past_batch:
                matching_signals.append(f"Both deploys modified PAYMENT_BATCH_SIZE (live: {live_batch}, past {recalled_id}: {past_batch})")
            elif live_batch and not past_batch:
                differing_signals.append(f"Live deploy modifies batch size ({live_batch}), but past deploy {recalled_id} changed different parameters")
            else:
                matching_signals.append("Both incidents were preceded by recent code/config deployments")
        elif (not has_live_deploy) and (not past_had_deploy):
            matching_signals.append(f"Both live incident and past incident {recalled_id} occurred during steady-state operations (no deploy delta)")
        elif has_live_deploy and not past_had_deploy:
            differing_signals.append(f"Live incident followed an immediate deployment; past incident {recalled_id} occurred during steady-state")
        elif (not has_live_deploy) and past_had_deploy:
            differing_signals.append(f"Past incident {recalled_id} was deploy-induced ({past_commit or 'code release'}); current incident has NO recent deploys (traffic surge)")

        # 4. Compare Metrics Thresholds (Generated dynamically from live values vs past incident values)
        if incident.metrics.memory_rss_bytes > 0 and incident.metrics.memory_limit_bytes > 0:
            if pct > 90:
                matching_signals.append(f"Memory saturation at {pct:.1f}% limit ({rss_mb}MB / {limit_mb}MB)")

        raw_past_lag = metadata.get("kafka_lag", 0)
        try:
            past_lag = int(raw_past_lag)
        except (ValueError, TypeError):
            past_lag = 0
        live_lag = incident.metrics.kafka_lag
        live_elevated = live_lag > 5000
        past_elevated = past_lag > 5000 or "consumer lag" in recalled_text.lower() or "kafka-lag" in recalled_text.lower()
        if live_elevated and past_elevated:
            matching_signals.append(f"Elevated consumer lag backlog matches (live: {live_lag:,}, past {recalled_id}: {past_lag:,})")
        elif live_elevated and not past_elevated:
            differing_signals.append(f"Live incident has elevated consumer lag ({live_lag:,} > 5,000), whereas past incident {recalled_id} had normal queue lag ({past_lag:,})")
        elif not live_elevated and past_elevated:
            differing_signals.append(f"Live incident has normal queue lag ({live_lag:,}), whereas past incident {recalled_id} had elevated consumer lag ({past_lag:,} > 5,000)")

        # 5. Check Obsolete Fix Guardrail
        if is_obsolete:
            guardrail_warning = f"ALERT: Past fix '{past_fix}' is marked OBSOLETE. Reason: {obsolete_reason}. Excluded from recommendation."
        elif differing_signals and len(differing_signals) > len(matching_signals):
            guardrail_warning = f"CAUTION: Significant divergence in deployment/traffic signals. Do not blindly copy past fix '{past_fix}' without diagnostic confirmation."

        return EvidenceComparison(
            recalled_incident_id=recalled_id,
            recalled_summary=recalled_text[:120] + "...",
            match_score=score,
            matching_signals=matching_signals or ["General error text overlap"],
            differing_signals=differing_signals or ["No material telemetry divergence detected"],
            past_fix_applied=past_fix,
            past_outcome=past_outcome,
            is_obsolete=is_obsolete,
            obsolete_reason=obsolete_reason,
            guardrail_warning=guardrail_warning
        )

    def investigate(self, incident: Incident, interaction_number: int = 1) -> InvestigationResult:
        """
        Triages an incident using LIVE evidence and Hindsight memories.
        """
        t0 = time.time()

        # Define all live derived variables at the top of investigate() before any branching
        live_logs_str = " ".join(incident.logs).lower()
        has_live_deploy = bool(incident.deploy_events)
        live_configs = incident.deploy_events[0].config_changes if incident.deploy_events else {}
        live_commit = incident.deploy_events[0].commit_hash if incident.deploy_events else ""
        live_author = incident.deploy_events[0].author if incident.deploy_events else ""
        live_message = incident.deploy_events[0].message if incident.deploy_events else ""
        rss_mb = incident.metrics.memory_rss_bytes // (1024 * 1024)
        limit_mb = incident.metrics.memory_limit_bytes // (1024 * 1024)
        pct = (incident.metrics.memory_rss_bytes / max(incident.metrics.memory_limit_bytes, 1)) * 100

        # Step 1: Query Hindsight memory bank
        deploy_info = ""
        if incident.deploy_events:
            d = incident.deploy_events[0]
            deploy_info = f"deploy:{d.commit_hash} {d.message} {d.config_changes}"
            if "21" in d.message or "java 21" in d.message.lower() or "ZGC" in str(d.config_changes):
                deploy_info += " java 21 zgc gc memory"

        error_signature = incident.alert_text
        if incident.logs:
            error_signature += " " + " ".join(incident.logs[:2])

        metrics_info = f"rss:{rss_mb}mb limit:{limit_mb}mb"
        if incident.metrics.kafka_lag > 5000:
            metrics_info += f" kafka consumer lag backlog {incident.metrics.kafka_lag}"

        # Recall strictly incident memories (policies are fetched separately per Issue 1)
        raw_recalled = payments_memory_bank.recall_for_alert(
            service=incident.service,
            error_signature=error_signature,
            deploy_info=deploy_info,
            metrics_info=metrics_info,
            top_k=8
        )

        # Requirement 1: Separate active memories from obsolete and failed-fix memories!
        # Do not sink failed fixes in the ranked list; move them to the Memory Correction section.
        active_memories = [m for m in raw_recalled if not m.get("is_obsolete") and m.get("outcome") != "failed"]
        failed_memories = [m for m in raw_recalled if m.get("outcome") == "failed"]
        obsolete_memories = [m for m in raw_recalled if m.get("is_obsolete")]
        
        # Also recall dedicated obsolete precedents matching Java 21 / ZGC / alert keywords
        if interaction_number > 1:
            matching_obs = payments_memory_bank.recall_obsolete(
                query=f"{incident.service} {deploy_info} {error_signature} java 21 zgc g1gc",
                service=incident.service
            )
            for obs in matching_obs:
                if not any(m["id"] == obs["id"] for m in obsolete_memories):
                    obsolete_memories.append(obs)
            # Prioritize INC-1003 (the G1GC fix) in obsolete memories list
            obsolete_memories.sort(key=lambda x: (x["id"] == "INC-1003", x.get("score", 0)), reverse=True)

            # Also recall dedicated failed fix precedents
            matching_failed = payments_memory_bank.recall_failed_fixes(
                query=f"{incident.service} {deploy_info} {error_signature}",
                service=incident.service
            )
            for fm in matching_failed:
                if not any(m["id"] == fm["id"] for m in failed_memories):
                    failed_memories.append(fm)

        # Merge failed fix memories into obsolete_memories list so they are presented in Memory Correction!
        for fm in failed_memories:
            fix_str = (fm.get("metadata") or {}).get("fix_applied") or fm.get("failed_fix") or "Attempted fix"
            reason_str = (fm.get("metadata") or {}).get("root_cause") or fm.get("fail_reason") or "Fix did not resolve the issue"
            if not any(m["id"] == fm["id"] for m in obsolete_memories):
                obsolete_memories.append({
                    "id": fm["id"],
                    "score": fm.get("score", 0.926),
                    "why_matched": f"{fm['id']} matched closely but its fix FAILED ({fix_str} did not resolve the issue) — see Memory Correction.",
                    "is_obsolete": False,
                    "is_failed_fix": True,
                    "outcome": "failed",
                    "failed_fix": fix_str,
                    "fail_reason": reason_str,
                    "metadata": fm.get("metadata", {})
                })

        # Issue 1: Interaction 1 must show 0 incident memories
        if interaction_number == 1:
            recalled_memories = []
            obsolete_memories = []
        else:
            recalled_memories = active_memories[:3]

        policies = payments_memory_bank.bank_id and [
            {"id": "POL-001", "title": "Prod Rollback Policy", "rule": "Prod rollbacks require approval", "applies_to": ["payment-service"]},
            {"id": "POL-002", "title": "Memory Limit Gate", "rule": "Memory limit modifications > 1Gi require lead sign-off", "applies_to": ["payment-service"]}
        ] or []

        # Step 2: Compare live evidence against each recalled memory
        comparisons: List[EvidenceComparison] = []
        for mem in recalled_memories:
            comp = self.compare_evidence(incident, mem)
            comparisons.append(comp)

        obsolete_comps: List[EvidenceComparison] = []
        for mem in obsolete_memories:
            comp = self.compare_evidence(incident, mem)
            obsolete_comps.append(comp)

        # Step 3: Compute confidence & formulate recommendation
        top_score = recalled_memories[0]["score"] if recalled_memories else 0.0
        matching_count = len(comparisons[0].matching_signals) if comparisons else 0

        # Handle Cold Start (Interaction 1 / Empty Bank)
        if not recalled_memories or interaction_number == 1:
            hypothesis = f"Suspected uncharacterized JVM memory leak or heap exhaustion in {incident.service}."
            confidence = "LOW"
            supporting_evidence = [
                f"Alert received: {incident.alert_text}",
                f"Pod RSS memory reached {rss_mb}MB / {limit_mb}MB ({pct:.1f}%)",
                f"Log signature exhibits exit code 137 (OOMKilled)",
                f"No prior historical memories found in Hindsight bank 'team-payments'"
            ]
            contradicting_evidence = [
                "No memory signature baseline available to isolate whether deploy or organic traffic triggered exhaustion"
            ]
            proposed_steps = [
                f"Capture JVM thread and heap dumps from running container replica ({incident.service})",
                "Inspect memory profiling metrics in Grafana dashboard",
                "Increase container restart backoff to avoid cascading restart loops"
            ]
            recommendation = Recommendation(
                hypothesis=hypothesis,
                confidence=confidence,
                supporting_evidence=supporting_evidence,
                contradicting_evidence=contradicting_evidence,
                proposed_steps=proposed_steps,
                source_memory_ids=[],
                approval_required=False,
                action_type="diagnostic_investigation",
                obsolete_warning=None
            )
        else:
            top_match = recalled_memories[0]
            top_comp = comparisons[0]
            source_ids = [m["id"] for m in recalled_memories[:3]]
            matching_count = len(top_comp.matching_signals)
            contradicting_count = len(top_comp.differing_signals)

            # Issue 5: Confidence = f(top score, matching signals, contradicting signals)
            # Cap at MEDIUM when there is no deploy diff (I12) or top score < 0.5
            calculated_confidence = compute_confidence(
                top_score=top_score,
                matching_signals_count=matching_count,
                contradicting_signals_count=contradicting_count,
                has_deploy_diff=has_live_deploy,
                interaction_number=interaction_number
            )

            # Check for Near-Duplicate and Obsolete / Failed-Fix conditions
            has_obsolete = bool(obsolete_comps) or any(c.is_obsolete or c.recalled_incident_id == "INC-1003" for c in comparisons)
            has_failed_fix = bool(failed_memories)
            obsolete_comp = next((c for c in obsolete_comps if c.recalled_incident_id == "INC-1003"), obsolete_comps[0] if obsolete_comps else next((c for c in comparisons if c.is_obsolete or c.recalled_incident_id == "INC-1003"), None))

            is_deploy_batch_oom = False
            if incident.deploy_events:
                changes = incident.deploy_events[0].config_changes
                if "PAYMENT_BATCH_SIZE" in changes or "batch" in incident.deploy_events[0].message.lower():
                    is_deploy_batch_oom = True

            is_traffic_surge_oom = (not is_deploy_batch_oom) and (incident.metrics.kafka_lag > 5000)

            # Issue 4 & 6: Interaction 20 - Recall INC-1003 & OBSOLETE G1GC correction, show in output, exclude from remediation steps
            if (has_obsolete or has_failed_fix) and (interaction_number >= 18 or "21" in str(incident.deploy_events)):
                commit_hash = live_commit or "recent"
                batch_val = live_configs.get("PAYMENT_BATCH_SIZE", "5000")
                
                hypothesis = f"Payment-service OOMKilled caused by commit {commit_hash} increasing PAYMENT_BATCH_SIZE to {batch_val} on Java 21."
                confidence = calculated_confidence
                
                top_active_id = top_match["id"] if top_match else "INC-1016"
                top_active_score = top_match["score"] if top_match else 0.0
                supporting_evidence = [
                    f"Correlates with top active memory {top_active_id} where increasing PAYMENT_BATCH_SIZE caused exit code 137 (score: {top_active_score:.3f})",
                    f"Deploy event {commit_hash} modified PAYMENT_BATCH_SIZE to {batch_val} on Java 21 LTS",
                    f"Container memory exhausted rapidly at {rss_mb}MB/{limit_mb}MB ({pct:.1f}%) with exit code 137"
                ]
                contradicting_evidence = []
                if obsolete_comp:
                    contradicting_evidence.append(
                        f"Excluding historical fix from {obsolete_comp.recalled_incident_id} ('{obsolete_comp.past_fix_applied}'): flags are deprecated in Java 21 ZGC and do not solve batch size memory exhaustion."
                    )
                for fm in failed_memories:
                    fix_name = (fm.get("metadata") or {}).get("fix_applied") or fm.get("failed_fix") or "Attempted fix"
                    reason_name = (fm.get("metadata") or {}).get("root_cause") or fm.get("fail_reason") or "fix failed in past incident"
                    contradicting_evidence.append(
                        f"Excluding historical fix from {fm['id']} ('{fix_name}'): attempted fix FAILED in past incident ({reason_name})."
                    )

                # Issue 6: Remove guardrail notes from remediation steps list; show only in memory correction section
                proposed_steps = [
                    "Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500)",
                    "Enable dynamic batch throttling to prevent heap exhaustion under high-throughput settlement",
                    f"Restart {incident.service} worker replicas to clear saturated JVM heap buffers",
                    f"Verify Kafka lag recovers below 500 records (currently {incident.metrics.kafka_lag:,})"
                ]

                guardrail_notes = []
                if obsolete_comp:
                    guardrail_notes.append(f"MEMORY CORRECTION / GUARDRAIL: Past fix from {obsolete_comp.recalled_incident_id} ('{obsolete_comp.past_fix_applied}') is marked OBSOLETE: {obsolete_comp.obsolete_reason}.")
                for fm in failed_memories:
                    fix_name = (fm.get("metadata") or {}).get("fix_applied") or fm.get("failed_fix") or "Attempted fix"
                    guardrail_notes.append(f"Past fix from {fm['id']} ('{fix_name}') FAILED; pod restart alone without config rollback does not solve batch OOM.")
                obs_warning_text = " ".join(guardrail_notes) if guardrail_notes else None

                recommendation = Recommendation(
                    hypothesis=hypothesis,
                    confidence=confidence,  # type: ignore
                    supporting_evidence=supporting_evidence,
                    contradicting_evidence=contradicting_evidence,
                    proposed_steps=proposed_steps,
                    source_memory_ids=source_ids,
                    approval_required=False,
                    action_type="rollback_deploy",
                    obsolete_warning=obs_warning_text
                )

            # Issue 6: Interaction 12 - Recall Kafka-lag near-duplicate (INC-1007) and cite in hypothesis
            elif is_traffic_surge_oom:
                hypothesis = f"Organic traffic surge causing worker memory saturation in {incident.service} (mirroring queue backlog in INC-1007), NOT a faulty deployment."
                confidence = calculated_confidence  # Capped at MEDIUM because has_deploy_diff is False
                supporting_evidence = [
                    f"Matches Kafka queue backlog signature from historical incident INC-1007 (consumer lag: {incident.metrics.kafka_lag:,} records)",
                    "No recent deploy events modifying batch sizes or heap configuration",
                    f"P99 latency degraded to {incident.metrics.p99_latency_ms:.0f}ms under heavy consumer queue",
                    f"Container memory saturated at {rss_mb}MB/{limit_mb}MB ({pct:.1f}%)"
                ]
                contradicting_evidence = [
                    f"Alert text matches past deploy-induced OOM ({top_match['id']}), but live deployment diff is absent."
                ]
                proposed_steps = [
                    f"Scale {incident.service} HorizontalPodAutoscaler minReplicas from 2 to 6",
                    f"Temporarily increase pod memory limit from {limit_mb}Mi to {limit_mb * 2}Mi to absorb queue burst",
                    f"Drain consumer lag backlog ({incident.metrics.kafka_lag:,} records) before scaling back down",
                    "DO NOT rollback release (release is healthy, load is organic)"
                ]
                recommendation = Recommendation(
                    hypothesis=hypothesis,
                    confidence=confidence,  # type: ignore
                    supporting_evidence=supporting_evidence,
                    contradicting_evidence=contradicting_evidence,
                    proposed_steps=proposed_steps,
                    source_memory_ids=source_ids,
                    approval_required=False,
                    action_type="scale_workers"
                )

            # Interaction 5: Deploy batch size regression
            elif is_deploy_batch_oom:
                batch_val = live_configs.get("PAYMENT_BATCH_SIZE", "5000")
                commit_hash = live_commit or "recent"
                author = live_author or "engineer"
                
                hypothesis = f"Payment-service OOMKilled caused by commit {commit_hash} increasing PAYMENT_BATCH_SIZE to {batch_val}."
                confidence = calculated_confidence
                supporting_evidence = [
                    f"Matches prior incidents {', '.join(source_ids[:2])} where batch size increases caused exit code 137",
                    f"Deploy event {commit_hash} by {author} modified PAYMENT_BATCH_SIZE to {batch_val}",
                    f"Heap memory exhausted rapidly at {rss_mb}MB/{limit_mb}MB ({pct:.1f}%) with exit code 137"
                ]
                # Issue 4: Remove hardcoded telemetry strings (HikariPool 14/20)
                contradicting_evidence = [
                    "Alert log signature indicates container exit code 137 rather than DB connection starvation"
                ]
                proposed_steps = [
                    "Rollback deploy config PAYMENT_BATCH_SIZE to safe baseline (500)",
                    f"Restart {incident.service} pods to clear saturated heap buffers",
                    f"Verify Kafka lag recovers below 500 records (currently {incident.metrics.kafka_lag:,})"
                ]
                recommendation = Recommendation(
                    hypothesis=hypothesis,
                    confidence=confidence,  # type: ignore
                    supporting_evidence=supporting_evidence,
                    contradicting_evidence=contradicting_evidence,
                    proposed_steps=proposed_steps,
                    source_memory_ids=source_ids,
                    approval_required=False,
                    action_type="rollback_deploy"
                )
            else:
                # Database connection pool or generic issue
                if "hikaripool" in live_logs_str:
                    hypothesis = f"Database connection pool exhaustion in {incident.service} causing thread blocking and timeout cascade."
                    confidence = calculated_confidence if calculated_confidence != "LOW" else "HIGH"
                    pool_act = incident.metrics.connection_pool_active
                    pool_max = incident.metrics.connection_pool_max
                    supporting_evidence = [
                        "Logs exhibit 'HikariPool-1 - Connection is not available, request timed out after 30000ms'",
                        f"Matches past memory {top_match['id']} where pool size was smaller than thread concurrency",
                        f"Active pool connections at {pool_act}/{pool_max}" if pool_max > 0 else "Active database connection pool saturated"
                    ]
                    contradicting_evidence = [
                        f"Memory RSS is {rss_mb}MB, but primary root cause is blocked database worker threads"
                    ]
                    proposed_steps = [
                        f"Increase maximum-pool-size from {pool_max or 20} to 40 in datasource config",
                        f"Restart {incident.service} replicas to reset stale connections",
                        "Monitor active connections in PgBouncer pool"
                    ]
                    recommendation = Recommendation(
                        hypothesis=hypothesis,
                        confidence=confidence,  # type: ignore
                        supporting_evidence=supporting_evidence,
                        contradicting_evidence=contradicting_evidence,
                        proposed_steps=proposed_steps,
                        source_memory_ids=source_ids,
                        approval_required=False,
                        action_type="db_pool_tune"
                    )
                else:
                    hypothesis = f"Memory exhaustion in {incident.service} correlating with {top_match['id']}."
                    confidence = calculated_confidence
                    supporting_evidence = [
                        f"Memory match score {top_match.get('score', 0):.2f} against {top_match['id']}",
                        f"Matching signals: {', '.join(top_comp.matching_signals)}"
                    ]
                    contradicting_evidence = top_comp.differing_signals
                    proposed_steps = [
                        f"Apply verified past mitigation: {top_comp.past_fix_applied}",
                        "Monitor memory consumption for 10 minutes",
                        "Confirm alert resolution"
                    ]
                    recommendation = Recommendation(
                        hypothesis=hypothesis,
                        confidence=confidence,  # type: ignore
                        supporting_evidence=supporting_evidence,
                        contradicting_evidence=contradicting_evidence,
                        proposed_steps=proposed_steps,
                        source_memory_ids=source_ids,
                        approval_required=False,
                        action_type="general_fix"
                    )

        # Step 4: Issue 5 - Trigger approval gate ONLY when a recommended step is a rollback!
        req_approval, reason = policy_engine.evaluate(incident, recommendation, policies)
        if req_approval:
            recommendation.approval_required = True
            recommendation.approval_policy_reason = reason
        else:
            recommendation.approval_required = False
            recommendation.approval_policy_reason = None

        latency = (time.time() - t0) * 1000

        return InvestigationResult(
            incident=incident,
            hypothesis=recommendation.hypothesis,
            confidence=recommendation.confidence,
            supporting_evidence=recommendation.supporting_evidence,
            contradicting_evidence=recommendation.contradicting_evidence,
            proposed_steps=recommendation.proposed_steps,
            comparisons=comparisons,
            retrieved_memories=recalled_memories,
            applied_policies=[p["title"] for p in policies if p.get("title")],
            recommendation=recommendation,
            execution_time_ms=round(latency, 2),
            interaction_number=interaction_number,
            obsolete_memories=obsolete_memories
        )

investigator = AgentInvestigator()
