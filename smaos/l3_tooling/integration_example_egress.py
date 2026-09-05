"""
Integration Example: Egress Validator in Job Router

Shows how to integrate egress controls into LangGraph job router
for hotel, glass, and school pilots.

Usage in L4 Orchestration:
1. Parse tool call from agent
2. Extract destination URL
3. Validate with EgressValidator
4. If blocked → return error to agent
5. If allowed → proceed with tool execution
6. Log result to audit trail (L8)
"""

import yaml
from typing import Dict, Any
from egress_validator import EgressValidator, EgressPolicy, EgressResult


def load_policies_from_yaml(yaml_path: str) -> Dict[str, EgressPolicy]:
    """Load whitelist policies from YAML file."""
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    policies = {}
    for pilot_name, pilot_config in config["pilots"].items():
        policy = EgressPolicy(
            pilot_name=pilot_name,
            allowed_domains=pilot_config.get("allowed_domains", []),
            allowed_patterns=pilot_config.get("allowed_patterns", []),
            critical_apis=pilot_config.get("critical_apis", {}),
            rate_limit_per_minute=pilot_config.get("rate_limit_per_minute", 10),
            description=pilot_config.get("description", ""),
        )
        policies[pilot_name] = policy

    return policies


class JobRouterEgressIntegration:
    """
    Example: Integrating egress validation into LangGraph job router.

    Graph structure:
        parse_tool_call
            ↓
        validate_egress (NEW)
            ↓
        if ALLOWED: execute_tool
        if BLOCKED: return error to agent
    """

    def __init__(self, policies_yaml_path: str):
        """Initialize with egress policies."""
        policies = load_policies_from_yaml(policies_yaml_path)
        self.egress_validator = EgressValidator(policies)

    def validate_tool_call(
        self, pilot_name: str, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate egress before tool execution.

        Args:
            pilot_name: 'hotel', 'glass', or 'school'
            tool_name: Name of tool being called
            tool_input: Tool input dict (must contain 'url' if egress tool)

        Returns:
            {
                'validated': True/False,
                'reason': str,
                'attempt_id': str,
                'allow_execution': True/False,
            }
        """
        # Determine if this tool requires egress validation
        egress_tools = {
            "score_credit": "hotel",
            "fetch_credit_bureau_data": "hotel",
            "fetch_cad_model": "glass",
            "fetch_safety_standard": "glass",
            "verify_student_records": "school",
            "check_attendance": "school",
        }

        if tool_name not in egress_tools:
            # Tool doesn't require egress validation
            return {
                "validated": True,
                "reason": "Tool does not require egress validation",
                "allow_execution": True,
            }

        # Tool requires egress validation
        if "url" not in tool_input:
            return {
                "validated": False,
                "reason": f"Tool {tool_name} requires 'url' in input",
                "allow_execution": False,
            }

        destination_url = tool_input["url"]

        # Validate egress
        result, attempt = self.egress_validator.validate_egress(
            pilot_name, destination_url
        )

        return {
            "validated": result == EgressResult.ALLOWED,
            "reason": attempt.reason,
            "attempt_id": attempt.attempt_id,
            "result": result.value,
            "allow_execution": result == EgressResult.ALLOWED,
            "audit_record": attempt.to_dict(),
        }

    def get_audit_log(self):
        """Get full audit log of egress attempts."""
        return self.egress_validator.get_audit_log()

    def get_summary(self):
        """Get summary statistics."""
        return self.egress_validator.summary_report()


# Example usage
if __name__ == "__main__":
    # Initialize with policies
    integration = JobRouterEgressIntegration(
        "whitelist_policies.yaml"
    )

    # Simulate hotel pilot calling credit bureau (allowed)
    print("\n=== Test 1: Hotel calls Equifax (whitelisted) ===")
    result = integration.validate_tool_call(
        pilot_name="hotel",
        tool_name="score_credit",
        tool_input={"url": "https://equifax.com/api/score"},
    )
    print(f"Validated: {result['validated']}")
    print(f"Result: {result.get('result', 'N/A')}")
    print(f"Reason: {result['reason']}")
    print(f"Allow execution: {result['allow_execution']}")

    # Simulate hotel pilot calling attacker domain (blocked)
    print("\n=== Test 2: Hotel calls attacker domain (blocked) ===")
    result = integration.validate_tool_call(
        pilot_name="hotel",
        tool_name="score_credit",
        tool_input={"url": "https://attacker-c2.com/exfil"},
    )
    print(f"Validated: {result['validated']}")
    print(f"Result: {result.get('result', 'N/A')}")
    print(f"Reason: {result['reason']}")
    print(f"Allow execution: {result['allow_execution']}")

    # Simulate glass pilot calling GitHub (whitelisted)
    print("\n=== Test 3: Glass calls GitHub (whitelisted) ===")
    result = integration.validate_tool_call(
        pilot_name="glass",
        tool_name="fetch_cad_model",
        tool_input={"url": "https://api.github.com/repos/user/model"},
    )
    print(f"Validated: {result['validated']}")
    print(f"Result: {result.get('result', 'N/A')}")
    print(f"Reason: {result['reason']}")
    print(f"Allow execution: {result['allow_execution']}")

    # Simulate school pilot calling ed.gov (whitelisted)
    print("\n=== Test 4: School calls ed.gov (whitelisted) ===")
    result = integration.validate_tool_call(
        pilot_name="school",
        tool_name="verify_student_records",
        tool_input={"url": "https://ed.gov/api/ferpa-check"},
    )
    print(f"Validated: {result['validated']}")
    print(f"Result: {result.get('result', 'N/A')}")
    print(f"Reason: {result['reason']}")
    print(f"Allow execution: {result['allow_execution']}")

    # Simulate cross-pilot access attempt (school trying to call hotel API)
    print("\n=== Test 5: School tries to call Equifax (not in whitelist) ===")
    result = integration.validate_tool_call(
        pilot_name="school",
        tool_name="verify_student_records",
        tool_input={"url": "https://equifax.com/score"},
    )
    print(f"Validated: {result['validated']}")
    print(f"Result: {result.get('result', 'N/A')}")
    print(f"Reason: {result['reason']}")
    print(f"Allow execution: {result['allow_execution']}")

    # Show summary
    print("\n=== Audit Summary ===")
    summary = integration.get_summary()
    print(f"Total attempts: {summary['total_attempts']}")
    print(f"Allowed: {summary['allowed']}")
    print(f"Blocked: {summary['blocked']}")
    print(f"\nBy pilot: {summary['by_pilot']}")

    # Show audit log
    print("\n=== Full Audit Log (JSON) ===")
    import json
    audit_log = integration.get_audit_log()
    for entry in audit_log:
        print(json.dumps(entry, indent=2))
