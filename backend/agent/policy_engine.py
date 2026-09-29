from typing import List, Dict, Any, Tuple
from backend.models import Incident, Recommendation

class PolicyEngine:
    """
    Evaluates team operational governance policies (retained in Hindsight)
    against agent recommendations.
    Rule: Trigger the approval gate only when a recommended step is a rollback.
    """
    def is_step_a_rollback(self, step: str) -> bool:
        s = step.lower().strip()
        # Explicit negation check: e.g. "DO NOT rollback release" is NOT a rollback!
        if (
            s.startswith("do not rollback") or 
            s.startswith("don't rollback") or 
            "no rollback" in s or 
            "avoid rollback" in s or
            "not a rollback" in s
        ):
            return False
        return (
            s.startswith("rollback") or 
            s.startswith("revert") or 
            " rollback " in f" {s} " or 
            " revert " in f" {s} "
        )

    def evaluate(self, incident: Incident, recommendation: Recommendation, policies: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Returns (approval_required: bool, reason: str).
        Strict Requirement: Trigger the approval gate only when a recommended step is a rollback.
        """
        action = recommendation.action_type.lower()
        has_rollback_step = any(self.is_step_a_rollback(st) for st in recommendation.proposed_steps)
        is_rollback_action = "rollback" in action or has_rollback_step

        # If none of the proposed steps is an actual rollback action, do NOT trigger approval gate!
        if not is_rollback_action:
            return False, ""

        for policy in policies:
            rule_id = policy.get("id", "POL-001")
            title = policy.get("title", "Prod Rollback Policy")
            rule = policy.get("rule", "")
            applies_to = [s.lower() for s in policy.get("applies_to", [])]

            if applies_to and incident.service.lower() not in applies_to:
                continue

            if "rollback" in rule.lower() or "rollback" in title.lower():
                return True, f"Policy [{rule_id} - {title}]: Automated rollback of {incident.service} in production requires explicit on-call engineer sign-off."

        return False, ""

policy_engine = PolicyEngine()
