# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_kagent_helm_generator.py
================================================================================
Test suite for kagent Helm & Kustomize Manifest Synthesis Engine.
Zero mocks, zero floats, deterministic validation.
"""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from typing import Any, Dict
import pytest

from src.kagent_helm_generator import HelmBundleArtifact, KagentHelmGenerator

SAMPLE_DIGEST = "sha256:aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"


def _build_manifest(kind: str, name: str) -> Dict[str, Any]:
    return {
        "apiVersion": "kagent.dev/v1alpha1",
        "kind": kind,
        "metadata": {
            "name": name,
            "namespace": "sovereign-system",
        },
        "spec": {
            "runtime": {
                "sandboxClass": "gvisor",
            },
            "security": {
                "spiffeId": f"spiffe://sovereign.nexus/ns/sovereign-system/sa/{name}/actor/lead",
            },
            "network": {
                "egressMode": "default-deny",
                "agentgatewayRef": "agentgateway.sovereign-system.svc.cluster.local:15001",
            },
            "env": [
                {"name": "API_SECRET", "value": "{{VAULT:API_SECRET}}"},
                {"name": "PORT", "value": "8080"},
            ],
            "lifecycle": {
                "eo1IntentLatch": True,
                "autopausePersistence": "sqlite-wal",
            },
            "governance": {
                "maxDriftThresholdBps": 4000,  # claim: config
                "maxBlastRadiusBps": 3000,  # claim: config
            },
        },
    }


def test_generate_bundle_valid() -> None:
    generator = KagentHelmGenerator()

    harness = _build_manifest("Harness", "sovereign-harness")
    template = _build_manifest("AgentTemplate", "sovereign-template")
    sandbox = _build_manifest("SandboxAgent", "sovereign-sandbox")

    bundle = generator.generate_bundle(
        chart_name="aeib-sovereign-mesh",
        chart_version="1.1.0",
        namespace="sovereign-system",
        harness_manifest=harness,
        agent_template_manifest=template,
        sandbox_agent_manifest=sandbox,
        bpf_lsm_profile_digest=SAMPLE_DIGEST,
    )

    assert bundle.chart_name == "aeib-sovereign-mesh"
    assert bundle.chart_version == "1.1.0"
    assert bundle.bundle_caid.startswith("sha256:")

    # Verify all expected files
    expected_files = {
        "Chart.yaml",
        "values.yaml",
        "templates/harness.yaml",
        "templates/agenttemplate.yaml",
        "templates/sandboxagent.yaml",
        "templates/tracingpolicy.yaml",
        "templates/agentgateway-route.yaml",
        "kustomization.yaml",
    }
    assert set(bundle.manifest_files.keys()) == expected_files

    # Verify content highlights
    assert "name: aeib-sovereign-mesh" in bundle.manifest_files["Chart.yaml"]
    assert "version: 1.1.0" in bundle.manifest_files["Chart.yaml"]
    assert "bpfLsmProfileDigest: " + SAMPLE_DIGEST in bundle.manifest_files["values.yaml"]
    
    tracing_yaml = bundle.manifest_files["templates/tracingpolicy.yaml"]
    assert "TracingPolicy" in tracing_yaml
    assert tracing_yaml.count("syscall: true") == 2
    assert tracing_yaml.count("index: 0") == 2
    assert "action: Sigkill" in tracing_yaml

    route_yaml = bundle.manifest_files["templates/agentgateway-route.yaml"]
    assert "RouteOption" in route_yaml
    assert "placeholderResolution: true" in route_yaml
    assert "headerRedaction: true" in route_yaml
    assert "mode: DefaultDeny" in route_yaml

    assert "Kustomization" in bundle.manifest_files["kustomization.yaml"]

    # Test serialization
    bundle_dict = bundle.to_dict()
    assert bundle_dict["chart_name"] == "aeib-sovereign-mesh"
    assert len(bundle_dict["manifest_files"]) == 8


def test_generate_bundle_validation_errors() -> None:
    generator = KagentHelmGenerator()

    harness = _build_manifest("Harness", "sovereign-harness")
    template = _build_manifest("AgentTemplate", "sovereign-template")
    sandbox = _build_manifest("SandboxAgent", "sovereign-sandbox")

    # Invalid chart name
    with pytest.raises(ValueError, match="ERR_INVALID_CHART_NAME"):
        generator.generate_bundle("", "1.0", "ns", harness, template, sandbox, SAMPLE_DIGEST)

    # Invalid chart version
    with pytest.raises(ValueError, match="ERR_INVALID_CHART_VERSION"):
        generator.generate_bundle("chart", "", "ns", harness, template, sandbox, SAMPLE_DIGEST)

    # Invalid namespace
    with pytest.raises(ValueError, match="ERR_INVALID_NAMESPACE"):
        generator.generate_bundle("chart", "1.0", "", harness, template, sandbox, SAMPLE_DIGEST)

    # Invalid BPF profile digest
    with pytest.raises(ValueError, match="ERR_INVALID_BPF_PROFILE_DIGEST"):
        generator.generate_bundle("chart", "1.0", "ns", harness, template, sandbox, "md5:bad")

    # Invalid Harness manifest (raw secret leak)
    bad_harness = _build_manifest("Harness", "bad-harness")
    bad_harness["spec"]["env"].append({"name": "LEAK", "value": "sk-123456789012345678901234567890"})
    with pytest.raises(ValueError, match="ERR_INVALID_HARNESS_MANIFEST"):
        generator.generate_bundle("chart", "1.0", "ns", bad_harness, template, sandbox, SAMPLE_DIGEST)

    # Invalid AgentTemplate manifest (bad drift cap)
    bad_template = _build_manifest("AgentTemplate", "bad-template")
    bad_template["spec"]["governance"]["maxDriftThresholdBps"] = 5000
    with pytest.raises(ValueError, match="ERR_INVALID_AGENT_TEMPLATE_MANIFEST"):
        generator.generate_bundle("chart", "1.0", "ns", harness, bad_template, sandbox, SAMPLE_DIGEST)

    # Invalid SandboxAgent manifest (bad runtime)
    bad_sandbox = _build_manifest("SandboxAgent", "bad-sandbox")
    bad_sandbox["spec"]["runtime"]["sandboxClass"] = "docker-runc"
    with pytest.raises(ValueError, match="ERR_INVALID_SANDBOX_AGENT_MANIFEST"):
        generator.generate_bundle("chart", "1.0", "ns", harness, template, bad_sandbox, SAMPLE_DIGEST)


def test_write_bundle_to_disk(tmp_path: Any) -> None:
    generator = KagentHelmGenerator()

    harness = _build_manifest("Harness", "harness-disk")
    template = _build_manifest("AgentTemplate", "template-disk")
    sandbox = _build_manifest("SandboxAgent", "sandbox-disk")

    bundle = generator.generate_bundle(
        chart_name="disk-chart",
        chart_version="1.0.0",
        namespace="disk-ns",
        harness_manifest=harness,
        agent_template_manifest=template,
        sandbox_agent_manifest=sandbox,
        bpf_lsm_profile_digest=SAMPLE_DIGEST,
    )

    out_dir = str(tmp_path / "kagent_chart")
    written = generator.write_bundle_to_disk(out_dir, bundle)

    assert len(written) == 8
    for p in written:
        assert os.path.exists(p)
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0


def test_dataclass_immutability() -> None:
    bundle = HelmBundleArtifact(
        chart_name="c",
        chart_version="1.0",
        manifest_files={},
        bundle_caid="sha256:1111",
    )
    with pytest.raises(FrozenInstanceError):
        bundle.chart_name = "mutated"  # type: ignore


def test_format_val_and_to_yaml_internals() -> None:
    # Test _format_val branches
    assert KagentHelmGenerator._format_val(None) == "null"
    assert KagentHelmGenerator._format_val(True) == "true"
    assert KagentHelmGenerator._format_val(False) == "false"
    assert KagentHelmGenerator._format_val(42) == "42"
    assert KagentHelmGenerator._format_val(3.14) == "3.14"
    assert KagentHelmGenerator._format_val("simple_identifier") == "simple_identifier"
    assert KagentHelmGenerator._format_val("key: value") == '"key: value"'
    assert KagentHelmGenerator._format_val('quote"in') == '"quote\\"in"'

    # Test _to_yaml indentation arithmetic and nested lists of dicts
    data = {
        "metadata": {
            "name": "test-pod",
        },
        "spec": {
            "containers": [
                {
                    "name": "c1",
                    "env": [
                        {"name": "VAR1", "value": "val1"},
                        {"name": "VAR2", "value": "val2"},
                    ],
                    "securityContext": {
                        "privileged": False,
                    },
                }
            ],
            "tags": ["prod", "aeib"],
        },
    }

    yaml_out = KagentHelmGenerator._to_yaml(data)
    assert 'metadata:\n  name: "test-pod"' in yaml_out
    assert "spec:\n  containers:" in yaml_out
    assert "  - name: c1" in yaml_out
    assert "    env:" in yaml_out
    assert "      - name: VAR1" in yaml_out
    assert "        value: val1" in yaml_out
    assert "    securityContext:" in yaml_out
    assert "        privileged: false" in yaml_out
    assert "  tags:\n    - prod\n    - aeib" in yaml_out

    # Test list item where first key is a dict
    dict_first = {
        "spec": {
            "rules": [
                {
                    "match": {
                        "prefix": "/api"
                    }
                }
            ]
        }
    }
    out_df = KagentHelmGenerator._to_yaml(dict_first)
    assert "spec:\n  rules:\n    - match:\n        prefix: /api" in out_df
