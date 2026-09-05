#!/usr/bin/env python3
"""
UNICREDIT DEMO ORCHESTRATOR
Runs all 5 systems in parallel (Sep 5-15)
Generates unified compliance report for Prague demo
"""

import subprocess
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

class DemoOrchestrator:
    """Master orchestrator for all 5 compliance systems"""

    SYSTEMS = {
        "eu_checker": {
            "module": "star_compliance/eu_checker.py",
            "name": "EU AI Act Checker",
            "days": 3,
            "priority": "HIGH",
        },
        "aiverify": {
            "module": "star_compliance/aiverify_runner.py",
            "name": "AI Verify Foundation",
            "days": 2,
            "priority": "HIGH",
        },
        "sad_paths": {
            "module": "star_adversarial/sad_paths.py",
            "name": "STAR Adversarial 12",
            "days": 4,
            "priority": "CRITICAL",
        },
        "granite": {
            "module": "star_ml/granite_lite.py",
            "name": "Granite TSFM",
            "days": 3,
            "priority": "MEDIUM",
        },
        "skills": {
            "module": "star_skills/skill_registry.py",
            "name": "DisCo AREX Skills",
            "days": 2,
            "priority": "STRETCH",
        },
    }

    def __init__(self):
        self.timestamp = datetime.utcnow().isoformat()
        self.base_path = Path("/Users/andriileukhin/Documents/SovereignNexus")
        self.results = {}

    def run_system(self, system_key: str, system_config: dict) -> dict:
        """Run a single system"""
        module_path = self.base_path / system_config["module"]

        try:
            result = subprocess.run(
                ["python3", str(module_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            return {
                "system": system_key,
                "name": system_config["name"],
                "status": "COMPLETED" if result.returncode == 0 else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except Exception as e:
            return {
                "system": system_key,
                "name": system_config["name"],
                "status": "ERROR",
                "error": str(e),
            }

    def run_all_systems_parallel(self) -> dict:
        """Execute all 5 systems in parallel"""
        print("\n" + "="*70)
        print("🚀 LAUNCHING ALL 5 SYSTEMS IN PARALLEL")
        print("="*70)
        print(f"\nTimestamp: {self.timestamp}")
        print(f"Target: UniCredit Demo (Sep 15)")
        print(f"Systems: {len(self.SYSTEMS)}")
        print()

        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.run_system, key, config): key
                for key, config in self.SYSTEMS.items()
            }

            for future in as_completed(futures):
                system_key = futures[future]
                try:
                    result = future.result()
                    results[system_key] = result
                    status_icon = "✅" if result["status"] == "COMPLETED" else "❌"
                    print(f"{status_icon} {result['name']}: {result['status']}")
                except Exception as e:
                    print(f"❌ {system_key}: ERROR - {e}")
                    results[system_key] = {"status": "ERROR", "error": str(e)}

        return results

    def generate_unified_report(self, system_results: dict) -> dict:
        """Generate unified compliance report"""
        completed_systems = [
            r for r in system_results.values() if r.get("status") == "COMPLETED"
        ]

        report = {
            "timestamp": self.timestamp,
            "demo_target": "UniCredit Prague (Sep 15)",
            "systems_total": len(self.SYSTEMS),
            "systems_completed": len(completed_systems),
            "status": "READY" if len(completed_systems) == len(self.SYSTEMS) else "IN_PROGRESS",
            "systems": {
                key: {
                    "name": self.SYSTEMS[key]["name"],
                    "status": result.get("status"),
                    "priority": self.SYSTEMS[key]["priority"],
                    "timeline_days": self.SYSTEMS[key]["days"],
                }
                for key, result in system_results.items()
            },
            "next_steps": [
                "Sep 5-7: Build Systems 1-4 foundation",
                "Sep 8: Notary meeting (show current state)",
                "Sep 9-11: Complete all systems + integration",
                "Sep 12-14: Full test + rehearsal",
                "Sep 15: UniCredit live demo",
            ],
            "demo_script": {
                "duration_minutes": 12,
                "components": [
                    "EU Compliance Score (541 → 850+)",
                    "AI Verify Results (4/9 → 9/9)",
                    "12 Sad Paths Blocked",
                    "Fraud Detection Live",
                    "5,000 Skills Available",
                ],
            },
        }

        return report

    def save_unified_report(self, report: dict, output_path: str = "reports/UNICREDIT_DEMO_STATUS.json") -> str:
        """Save unified status report"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Unified report saved: {output_path}")
        return output_path

    def print_summary(self, report: dict):
        """Print summary to console"""
        print("\n" + "="*70)
        print("UNICREDIT DEMO: PARALLEL BUILD STATUS")
        print("="*70)

        print(f"\nDEMO TARGET: {report['demo_target']}")
        print(f"STATUS: {report['status']}")
        print(f"Systems Completed: {report['systems_completed']}/{report['systems_total']}")

        print(f"\nSYSTEMS:")
        for system_key, system_info in report["systems"].items():
            status_icon = "✅" if system_info["status"] == "COMPLETED" else "🔄"
            print(f"  {status_icon} {system_info['name']:35} [{system_info['priority']}]")

        print(f"\nNEXT STEPS:")
        for step in report["next_steps"]:
            print(f"  • {step}")

        print(f"\nDEMO SCRIPT (12 minutes):")
        for i, component in enumerate(report["demo_script"]["components"], 1):
            print(f"  {i}. {component}")

        print("\n" + "="*70)
        print("🌍⚖️🔐 ALL SYSTEMS LAUNCHING IN PARALLEL")
        print("="*70 + "\n")


if __name__ == "__main__":
    orchestrator = DemoOrchestrator()

    # Run all systems in parallel
    system_results = orchestrator.run_all_systems_parallel()

    # Generate unified report
    report = orchestrator.generate_unified_report(system_results)

    # Save and print
    orchestrator.save_unified_report(report)
    orchestrator.print_summary(report)
