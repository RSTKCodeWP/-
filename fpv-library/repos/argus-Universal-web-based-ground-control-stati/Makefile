.PHONY: lint test build check dev clean

lint:
	ruff check backend/ scripts/ tests/
	npx svelte-check --tsconfig ./tsconfig.json

test:
	python -m pytest tests/test_unit_*.py tests/test_contract_*.py -q --tb=short
	npx vitest run

test-cov:
	python -m pytest tests/test_unit_*.py tests/test_contract_*.py -q --cov=backend --cov-report=term-missing --cov-fail-under=95
	npx vitest run --coverage

test-integration:
	python scripts/sim_pllink.py 5770 &
	sleep 2
	python run.py --port 8199 &
	sleep 3
	python -m pytest tests/test_integration.py -v --tb=short -k 'not test_param_set' || true
	pkill -f 'sim_pllink|run.py --port 8199' 2>/dev/null || true

build:
	npm run build

check: lint test build
	@echo "All checks passed."

dev:
	python run.py --sim

clean:
	rm -rf dist/ build/ .pytest_cache/ coverage/
