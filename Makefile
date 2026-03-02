.PHONY: dev-up dev-down dev-logs migrate migrate-down migrate-history \
        install install-dev test test-unit test-integration test-scenarios \
        lint format typecheck clean

# ── Docker Services ───────────────────────────────────────────────────────────

dev-up:
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@docker compose wait postgres redis minio || true
	@echo "Services running. Postgres: 5432 | MinIO: 9000 | Prefect: 4200"

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

dev-reset:
	docker compose down -v
	docker compose up -d

# ── Database Migrations ───────────────────────────────────────────────────────

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-history:
	alembic history --verbose

migrate-new:
	@read -p "Migration name: " name; alembic revision --autogenerate -m "$$name"

# ── Python Dependencies ───────────────────────────────────────────────────────

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-scenarios:
	pytest tests/scenarios/ -v --tb=short -s

test-cov:
	pytest tests/ --cov=src/advocate --cov-report=term-missing --cov-report=html

# ── Code Quality ──────────────────────────────────────────────────────────────

lint:
	ruff check src/ tests/
	mypy src/advocate/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/advocate/

# ── Application ───────────────────────────────────────────────────────────────

api:
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python apps/worker/main.py

# ── Utilities ─────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
