# AEIB Clean-Room Build and Verification Automation
.PHONY: help test check ast-purity diff-engine cleanroom-build cleanroom-test cleanroom-shell clean

help:
	@echo "AEIB Independent Verification Targets:"
	@echo "  make test             Run local pytest suite across financial boundary and chaos tests"
	@echo "  make ast-purity       Execute zero-mock AST purity scanners"
	@echo "  make diff-engine      Run Java vs Python cross-language differential parity engine"
	@echo "  make cleanroom-build  Build pinned Docker clean-room audit container"
	@echo "  make cleanroom-test   Run full verification suite inside clean-room container"
	@echo "  make cleanroom-shell  Launch interactive shell in clean-room container"

test:
	python3 -m pytest tests/test_governed_financial_action_boundary.py tests/test_production_readiness_chaos_harness.py tests/test_action_intelligence_brief.py -v

ast-purity:
	python3 compliance/ast_purity.py .
	python3 compliance/no_mock_enforcer.py

diff-engine:
	python3 benchmarks/jvm_native_diff_engine.py

check: ast-purity test diff-engine

cleanroom-build:
	docker build --build-arg GIT_COMMIT=$$(git rev-parse HEAD) -f Dockerfile.cleanroom -t aeib-cleanroom:latest .

cleanroom-test:
	docker run --rm \
	  --mount type=bind,source="$$(pwd)/audit_out",target=/app/audit_out \
	  aeib-cleanroom:latest \
	  /bin/bash -c "python3 compliance/ast_purity.py . && python3 compliance/no_mock_enforcer.py && python3 verify-audit-pack.py && python3 -m pytest tests/test_production_readiness_chaos_harness.py -v && python3 benchmarks/jvm_native_diff_engine.py"

cleanroom-shell:
	mkdir -p audit_out
	docker run -it --rm \
	  --mount type=bind,source="$$(pwd)/audit_out",target=/app/audit_out \
	  aeib-cleanroom:latest /bin/bash

clean:
	rm -rf audit_out/ .pytest_cache/
