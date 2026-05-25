.PHONY: run up down logs status test eval backend-test frontend-build frontend-audit typecheck docker-check clean doctor

run: up

up:
	./run

status:
	./run status

down:
	./run stop

logs:
	./run logs

test:
	./run test

eval:
	./run eval

backend-test:
	cd backend && ../.venv/bin/python -m pytest -q tests --ignore=tests/integration

frontend-build:
	cd frontend && npm run build

frontend-audit:
	cd frontend && npm audit --audit-level=moderate

typecheck:
	cd backend && PYTHONPATH=. ../.venv/bin/mypy

docker-check:
	docker compose --env-file .env.example config >/dev/null

clean:
	./run clean

doctor:
	./run doctor
