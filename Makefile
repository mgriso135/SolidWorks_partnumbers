.PHONY: install backend-install frontend-install dev dev-ui build test lint format clean migrate migration connector-build connector-test docker-build up down logs

install: backend-install frontend-install
	@test -f .env || cp .env.example .env

backend-install:
	cd backend && test -d .venv || python3 -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt

frontend-install:
	cd frontend && npm install

dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload $(shell test -f .env && echo --env-file ../.env)

dev-ui:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

test:
	cd backend && .venv/bin/pytest

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run build

format:
	cd backend && .venv/bin/ruff format .

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
	find pdm-connector -type d \( -name bin -o -name obj \) -prune -exec rm -rf {} +

migrate:
	cd backend && .venv/bin/alembic upgrade head

migration:
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

docker-build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

connector-build:
	dotnet build pdm-connector/PartCode.Connector.slnx -c Release

connector-test:
	dotnet test pdm-connector/PartCode.Connector.slnx
