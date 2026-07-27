SHELL := /bin/bash

UV_CACHE_DIR ?= /tmp/uv-cache
DOCKER_TEST_COMPOSE := docker compose -f docker-compose.test.yml

.PHONY: \
	backend-lint \
	backend-format-check \
	backend-typecheck \
	backend-test \
	backend-security \
	backend-dependency-audit \
	backend-seed-auth \
	backend-check \
	frontend-lint \
	frontend-format-check \
	frontend-typecheck \
	frontend-test-unit \
	frontend-test-e2e \
	frontend-dependency-audit \
	frontend-check \
	security-check \
	production-readiness-check \
	backup-postgres-dry-run \
	backup-minio-dry-run \
	frontend-check-e2e \
	check \
	perf-users-list \
	perf-users-export \
	docker-test-backend \
	docker-test-frontend \
	docker-test-e2e \
	docker-test \
	migrate \
	migrate-refresh \
	seed

backend-lint:
	cd backend && if [ -x .venv/bin/ruff ]; then .venv/bin/ruff check .; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check .; fi

backend-format-check:
	cd backend && if [ -x .venv/bin/ruff ]; then .venv/bin/ruff format --check .; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff format --check .; fi

backend-typecheck:
	cd backend && if [ -x .venv/bin/mypy ]; then .venv/bin/mypy .; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run mypy .; fi

backend-test:
	cd backend && if [ -x .venv/bin/pytest ]; then .venv/bin/pytest tests --cov=app --cov-report=term-missing; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest tests --cov=app --cov-report=term-missing; fi

backend-security:
	cd backend && if [ -x .venv/bin/bandit ]; then .venv/bin/bandit -c pyproject.toml -r app; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run bandit -c pyproject.toml -r app; fi

backend-dependency-audit:
	cd backend && if [ -x .venv/bin/pip-audit ]; then XDG_CACHE_HOME=/tmp/.cache .venv/bin/pip-audit; else XDG_CACHE_HOME=/tmp/.cache UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pip-audit; fi

backend-seed-auth:
	cd backend && if [ -x .venv/bin/python ]; then .venv/bin/python scripts/seed_auth_rbac.py; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run python scripts/seed_auth_rbac.py; fi

backend-check: backend-lint backend-format-check backend-typecheck backend-test backend-security

frontend-lint:
	npm --prefix frontend run lint

frontend-format-check:
	npm --prefix frontend run format:check

frontend-typecheck:
	npm --prefix frontend run typecheck

frontend-test-unit:
	npm --prefix frontend run test:unit

frontend-test-e2e:
	npm --prefix frontend run test:e2e

frontend-dependency-audit:
	NPM_CONFIG_CACHE=/tmp/.npm npm --prefix frontend audit --audit-level=high

frontend-check: frontend-lint frontend-format-check frontend-typecheck frontend-test-unit

security-check: backend-security backend-dependency-audit frontend-dependency-audit

production-readiness-check:
	bash scripts/compliance/check-production-readiness.sh

backup-postgres-dry-run:
	DRY_RUN=true bash scripts/ops/backup-postgres.sh

backup-minio-dry-run:
	DRY_RUN=true bash scripts/ops/backup-minio.sh

frontend-check-e2e: frontend-check frontend-test-e2e

check: backend-check frontend-check

perf-users-list:
	cd backend && if [ -x .venv/bin/python ]; then .venv/bin/python ../scripts/perf/check_users_list.py; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run python ../scripts/perf/check_users_list.py; fi

perf-users-export:
	cd backend && if [ -x .venv/bin/python ]; then .venv/bin/python ../scripts/perf/check_users_export.py; else UV_CACHE_DIR=$(UV_CACHE_DIR) uv run python ../scripts/perf/check_users_export.py; fi

docker-test-backend:
	$(DOCKER_TEST_COMPOSE) run --build --rm backend-test

docker-test-frontend:
	$(DOCKER_TEST_COMPOSE) run --build --rm frontend-test

docker-test-e2e:
	$(DOCKER_TEST_COMPOSE) run --build --rm e2e-test

docker-test: docker-test-backend docker-test-frontend docker-test-e2e

migrate:
	docker compose exec backend uv run alembic upgrade head

migrate-refresh:
	docker compose exec backend uv run alembic downgrade base
	docker compose exec backend uv run alembic upgrade head

seed:
	docker compose exec backend uv run python scripts/seed_auth_rbac.py
