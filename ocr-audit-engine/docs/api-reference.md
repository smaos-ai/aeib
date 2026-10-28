# API Reference: OCR Audit Engine

## Core Classes

### `DeterministicDispatcher`
```python
from ocr_audit.dispatcher import DeterministicDispatcher, TraceRecord

dispatcher = DeterministicDispatcher(filter_read_only=True, filter_healthy_reads=True)
selected_traces, metrics = dispatcher.dispatch(traces)
```

### `SmartActionBundler`
```python
from ocr_audit.bundler import SmartActionBundler

bundler = SmartActionBundler(window_seconds=5.0)
bundles = bundler.bundle(selected_traces)
```

### `ForensicInterrogator`
```python
from ocr_audit.interrogator import ForensicInterrogator

interrogator = ForensicInterrogator()
candidate_findings = interrogator.evaluate_bundle(bundle)
```

### `WireTruthReflector`
```python
from ocr_audit.reflector import WireTruthReflector

is_valid, reason = WireTruthReflector.verify(candidate_finding, bundle)
```

### `DeterministicAnchor`
```python
from ocr_audit.anchor import DeterministicAnchor

verified_finding = DeterministicAnchor.anchor(candidate_finding, bundle, target_filename="traces.jsonl")
```

### `HybridAuditPipeline`
```python
from ocr_audit.pipeline_runner import HybridAuditPipeline

pipeline = HybridAuditPipeline(Path("traces.jsonl"), window_seconds=5.0)
results = pipeline.run()
patch = pipeline.generate_remediation_patch(results)
```
