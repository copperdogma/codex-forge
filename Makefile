# Makefile for codex-forge smoke tests

.PHONY: smoke smoke-ff

smoke: smoke-ff

smoke-ff:
	@echo "Running Fighting Fantasy smoke test (stubbed, no AI calls)..."
	PYTHONPATH=. python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --force
	@echo "Smoke test complete. Artifacts in output/runs/smoke-ff/"
	@echo "Checking validation report..."
	@grep '"is_valid": true' output/runs/smoke-ff/validation_report.json > /dev/null || (echo "Validation FAILED" && exit 1)
	@echo "Validation PASSED"
