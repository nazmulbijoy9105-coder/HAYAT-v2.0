.PHONY: help install test lint build deploy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

dev: ## Start development environment
	docker-compose up -d postgres neo4j redis opensearch qdrant minio rabbitmq
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev &

test: ## Run all tests
	cd backend && pytest tests/ -v --cov=app --cov-report=html
	cd frontend && npm run test

lint: ## Run linters
	cd backend && black app/ tests/ && ruff check app/ tests/
	cd frontend && npm run lint

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create new migration
	cd backend && alembic revision --autogenerate -m "$(msg)"

build: ## Build Docker images
	docker-compose build

build-push: ## Build and push to registry
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml push

deploy-staging: ## Deploy to staging
	kubectl apply -k k8s/overlays/staging/

deploy-prod: ## Deploy to production
	kubectl apply -k k8s/overlays/production/

backup: ## Run manual backup
	./scripts/backup/backup.sh

logs: ## View logs
	docker-compose logs -f api worker

clean: ## Clean up
	docker-compose down -v
	docker system prune -f
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
