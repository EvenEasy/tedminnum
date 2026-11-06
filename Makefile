.PHONY: check test web
check:
	cd backend && uv run ruff check src tests migrations && uv run ruff format --check src tests migrations && uv run mypy src
	cd frontend && npm run typecheck && npm run format:check && npm run build
test:
	cd backend && uv run pytest -q
web:
	cd frontend && npm run test:e2e
