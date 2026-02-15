# ─────────────────────────────────────────────────────────────────────────────
#  CinematchAI — One-command control
#  Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help plugin up down restart build build-api build-frontend \
        logs logs-api logs-frontend logs-monitor \
        monitor ps shell-api shell-frontend \
        k8s-apply k8s-delete k8s-status \
        dev dev-api dev-frontend clean

COMPOSE := docker compose
KUBECTL  := kubectl
NS       := cinematch

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD  := \033[1m
RESET := \033[0m
GOLD  := \033[33m

help:  ## Show this help message
	@echo "$(BOLD)$(GOLD)CinematchAI — Docker/K8s control$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN{FS=":.*?## "} {printf "  $(BOLD)%-20s$(RESET) %s\n", $$1, $$2}'

# ── Docker Compose ────────────────────────────────────────────────────────────

plugin: ## Install Loki Docker driver plugin (run ONCE before `make up`)
	@echo "$(BOLD)Installing Loki Docker driver plugin…$(RESET)"
	@docker plugin install grafana/loki-docker-driver:3.0.0 --alias loki --grant-all-permissions || \
	  echo "$(GOLD)Plugin already installed — continuing$(RESET)"
	@docker plugin ls | grep loki

up: ## Start all services — run `make plugin` first if using Loki log driver
	$(COMPOSE) up -d --remove-orphans
	@echo ""
	@echo "$(BOLD)$(GOLD)Services started:$(RESET)"
	@echo "  Frontend  → http://localhost:3000"
	@echo "  API       → http://localhost:8000"
	@echo "  API docs  → http://localhost:8000/docs"
	@echo "  Grafana   → http://localhost:3001  (admin / cinematch)"
	@echo "  Prometheus→ http://localhost:9090"
	@echo "  Loki      → http://localhost:3100"

down: ## Stop and remove all containers
	$(COMPOSE) down

restart: ## Restart all containers
	$(COMPOSE) restart

build: ## Build all Docker images
	$(COMPOSE) build --no-cache

build-api: ## Build only the API image
	$(COMPOSE) build --no-cache api

build-frontend: ## Build only the frontend image
	$(COMPOSE) build --no-cache frontend

ps: ## Show running containers and health
	$(COMPOSE) ps

# ── Logs ──────────────────────────────────────────────────────────────────────

logs: ## Tail logs from all containers
	$(COMPOSE) logs -f --tail=50

logs-api: ## Tail API logs only
	$(COMPOSE) logs -f --tail=100 api

logs-frontend: ## Tail frontend (nginx) logs only
	$(COMPOSE) logs -f --tail=50 frontend

logs-monitor: ## Tail Prometheus + Grafana + Loki logs
	$(COMPOSE) logs -f --tail=30 prometheus grafana loki

# ── Shells ────────────────────────────────────────────────────────────────────

shell-api: ## Open a bash shell inside the running API container
	$(COMPOSE) exec api /bin/bash

shell-frontend: ## Open a shell inside the nginx container
	$(COMPOSE) exec frontend /bin/sh

# ── Monitoring shortcuts ──────────────────────────────────────────────────────

monitor: ## Open Grafana in browser (macOS / Linux)
	@which open >/dev/null 2>&1 && open http://localhost:3001 || \
	  xdg-open http://localhost:3001 2>/dev/null || \
	  echo "Open http://localhost:3001 in your browser"

# ── Local development (no Docker) ────────────────────────────────────────────

dev: ## Start API + frontend locally (no Docker)
	@echo "$(BOLD)Starting API on :8000 and frontend on :5173…$(RESET)"
	@$(MAKE) dev-api &
	@$(MAKE) dev-frontend

dev-api: ## Start FastAPI dev server locally
	PYTHONPATH=. uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start Vite dev server locally
	cd frontend && npm run dev

# ── Kubernetes ────────────────────────────────────────────────────────────────

k8s-apply: ## Apply all K8s manifests to the cluster
	$(KUBECTL) apply -f infra/k8s/namespace.yml
	$(KUBECTL) apply -f infra/k8s/api.yml
	$(KUBECTL) apply -f infra/k8s/frontend.yml
	$(KUBECTL) apply -f infra/k8s/monitoring.yml
	$(KUBECTL) apply -f infra/k8s/ingress.yml
	@echo "$(BOLD)$(GOLD)K8s resources applied to namespace '$(NS)'$(RESET)"

k8s-delete: ## Delete all K8s resources (WARNING: destroys data)
	$(KUBECTL) delete namespace $(NS) --ignore-not-found

k8s-status: ## Show pod/service status in the cinematch namespace
	$(KUBECTL) get pods,svc,ingress -n $(NS)

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove stopped containers, unused images, and build cache
	docker system prune -f
	docker volume prune -f
	@echo "$(BOLD)Docker cleanup complete$(RESET)"
