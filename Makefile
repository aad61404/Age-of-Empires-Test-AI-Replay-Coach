.PHONY: install test lint format typecheck check doctor

install:
	cd backend && uv sync --locked

test:
	cd backend && uv run --locked pytest --cov=aoe2coach

lint:
	cd backend && uv run --locked ruff check src tests
	cd backend && uv run --locked ruff format --check src tests

format:
	cd backend && uv run --locked ruff format src tests

typecheck:
	cd backend && uv run --locked mypy src

check: lint typecheck test

doctor:
	cd backend && uv run --locked aoe2coach doctor
