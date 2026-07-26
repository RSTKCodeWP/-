.PHONY: help install dev-install test lint format clean run docker-build docker-up docker-down migrate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

dev-install: ## Install development dependencies
	pip install -r requirements.txt
	pre-commit install

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=term-missing

test-fast: ## Run tests without coverage
	pytest tests/ -v

lint: ## Run linters
	black --check app tests
	isort --check-only app tests
	flake8 app tests --max-line-length=100 --extend-ignore=E203,W503
	mypy app --ignore-missing-imports --no-strict-optional

format: ## Format code
	black app tests
	isort app tests

clean: ## Clean up cache and build files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml

run: ## Run the bot
	python -m app.main

docker-build: ## Build Docker image
	docker build -t oleg-bot:latest .

docker-rebuild: ## Rebuild Docker image without cache
	docker-compose build --no-cache

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-restart: ## Restart bot container
	docker-compose restart oleg-bot

docker-update: ## Full update: rebuild and restart
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

docker-logs: ## Show Docker logs
	docker-compose logs -f oleg-bot

docker-logs-all: ## Show all containers logs
	docker-compose logs -f

docker-shell: ## Open shell in bot container
	docker-compose exec oleg-bot /bin/bash

docker-status: ## Show containers status
	docker-compose ps

migrate-create: ## Create new migration (usage: make migrate-create MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

migrate-up: ## Apply migrations
	alembic upgrade head

migrate-down: ## Rollback last migration
	alembic downgrade -1

migrate-history: ## Show migration history
	alembic history

db-init: ## Initialize database
	python -c "import asyncio; from app.database.session import init_db; asyncio.run(init_db())"

security-check: ## Run security checks
	safety check
	bandit -r app

pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files

update-deps: ## Update dependencies
	pip list --outdated
	@echo "Run 'pip install --upgrade <package>' to update"

check: lint test ## Run all checks (lint + test)

all: clean format lint test ## Clean, format, lint and test
