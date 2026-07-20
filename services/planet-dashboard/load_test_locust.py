#!/usr/bin/env python3
"""
Locust load test for Vision API
Target: 1,000 requests/second, p99 latency <100ms
Run with: locust -f load_test_locust.py -H http://localhost:8000
"""

from locust import HttpUser, task, between
import random
import string


class VisionAPIUser(HttpUser):
    """Simulated user making govern requests"""

    wait_time = between(0.001, 0.01)  # 1-10ms between requests (simulates ~1K req/sec)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_counter = 0

    @task(weight=70)
    def govern_low_risk(self):
        """70% low-risk requests (auto-approved)"""
        self.request_counter += 1
        payload = {
            "request_id": f"load-low-{self.request_counter}",
            "action": "read_file",
            "blast_radius": 0.1,
            "user_id": f"user-{random.randint(1, 100)}",
            "app_id": f"app-{random.randint(1, 10)}",
            "human_approved": False,
        }

        with self.client.post(
            "/v1/govern",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("approved") == True and data.get("charge_amount") == 100:
                    response.success()
                else:
                    response.failure(f"Unexpected response: {data}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")

    @task(weight=20)
    def govern_medium_risk(self):
        """20% medium-risk requests"""
        self.request_counter += 1
        payload = {
            "request_id": f"load-med-{self.request_counter}",
            "action": "write_config",
            "blast_radius": 0.4,
            "user_id": f"user-{random.randint(1, 100)}",
            "app_id": f"app-{random.randint(1, 10)}",
            "human_approved": False,
        }

        with self.client.post(
            "/v1/govern",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("approved") == True:
                    response.success()
                else:
                    response.failure(f"Unexpected response: {data}")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(weight=10)
    def govern_high_risk_approved(self):
        """10% high-risk requests WITH approval"""
        self.request_counter += 1
        payload = {
            "request_id": f"load-high-{self.request_counter}",
            "action": "execute_command",
            "blast_radius": 0.8,
            "user_id": f"admin-{random.randint(1, 10)}",
            "app_id": f"app-{random.randint(1, 10)}",
            "human_approved": True,  # APPROVED
        }

        with self.client.post(
            "/v1/govern",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("approved") == True and data.get("charge_amount") == 100:
                    response.success()
                else:
                    response.failure(f"Expected approval but got: {data}")
            else:
                response.failure(f"HTTP {response.status_code}")


if __name__ == "__main__":
    # For manual testing (requires running Locust UI)
    import subprocess
    subprocess.run([
        "locust",
        "-f", __file__,
        "-H", "http://localhost:8000",
        "--headless",
        "--users", "100",
        "--spawn-rate", "10",
        "--run-time", "60s",
    ])
