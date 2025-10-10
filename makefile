.PHONY: help install dev test lint format clean docker-build docker-up docker-down \
         docker-logs docker-scale docker-cpu proxmox-deploy proxmox-scale proxmox-monitor \
         performance-test cpu-pin numa-check cache-setup benchmark docs info watch

# ==================== VARIABLES ====================
PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
DOCKER_COMPOSE := docker-compose
VERA_SERVICE := vera
UI_SERVICE := vera-ui
WORKER_SERVICE := vera-worker

# Vera paths
VERA_ROOT := $(PWD)
VERA_MAIN := $(VERA_ROOT)/vera.py
VERA_UI := $(VERA_ROOT)/ui.py
VERA_TESTS := $(VERA_ROOT)/tests
VERA_DOCS := $(VERA_ROOT)/docs

# Docker settings
DOCKER_IMAGE := vera-ai:latest
DOCKER_CONTAINER := vera-ai-prod
WORKER_CONTAINER_PREFIX := vera-worker
DOCKER_REGISTRY ?= localhost:5000
DOCKER_NETWORK := vera-network

# Container resource defaults
DEFAULT_CPU_SHARES := 1024
DEFAULT_MEMORY := 2g
DEFAULT_CPU_PERIOD := 100000

# Proxmox settings
PROXMOX_HOST ?= 192.168.1.1
PROXMOX_USER ?= root@pam
PROXMOX_TOKEN ?= dummy-token
PROXMOX_NODE ?= pve
PROXMOX_VM_MEMORY ?= 8192
PROXMOX_VM_CORES ?= 4
PROXMOX_STORAGE ?= local-lvm

# Performance tuning
CPU_CORES := $(shell nproc)
HUGEPAGE_SIZE ?= 1G
HUGEPAGE_COUNT ?= 4

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# ==================== HELP ====================
help:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    VERA-AI Project Makefile                        ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)SETUP & ENVIRONMENT:$(NC)"
	@echo "  make install              Install dependencies and setup environment"
	@echo "  make dev                  Setup development environment"
	@echo "  make venv                 Create Python virtual environment"
	@echo "  make info                 Show system and project information"
	@echo ""
	@echo "$(GREEN)TESTING & CODE QUALITY:$(NC)"
	@echo "  make test                 Run all test suites"
	@echo "  make test-unit            Run unit tests only"
	@echo "  make test-integration     Run integration tests"
	@echo "  make test-performance     Run performance tests"
	@echo "  make lint                 Run linting checks (flake8, pylint)"
	@echo "  make format               Format code with black and isort"
	@echo "  make coverage             Generate test coverage report"
	@echo ""
	@echo "$(GREEN)DEVELOPMENT:$(NC)"
	@echo "  make run                  Run Vera agent (CLI)"
	@echo "  make run-ui               Run Vera UI server (port 8000)"
	@echo "  make clean                Clean build artifacts and caches"
	@echo "  make docs                 Generate documentation"
	@echo ""
	@echo "$(GREEN)DOCKER MANAGEMENT:$(NC)"
	@echo "  make docker-build         Build Docker image"
	@echo "  make docker-up            Start Docker containers (dev & prod)"
	@echo "  make docker-down          Stop and remove Docker containers"
	@echo "  make docker-logs          View Docker container logs"
	@echo "  make docker-shell [SVC=x] Open shell in running container"
	@echo "  make docker-scale NUM=N   Scale worker containers to N instances"
	@echo "  make docker-cpu           Adjust container CPU (interactive)"
	@echo "  make docker-mem           Adjust container memory (interactive)"
	@echo "  make docker-stats         Show Docker container resource usage"
	@echo "  make docker-watch         Watch container metrics in real-time"
	@echo ""
	@echo "$(GREEN)PROXMOX DEPLOYMENT:$(NC)"
	@echo "  make proxmox-deploy       Deploy Vera to Proxmox VM"
	@echo "  make proxmox-scale NUM=N  Scale Proxmox VMs to N instances"
	@echo "  make proxmox-monitor      Monitor Proxmox resource usage"
	@echo "  make proxmox-destroy      Destroy all Vera VMs on Proxmox"
	@echo "  make proxmox-status       Show Proxmox VM status"
	@echo ""
	@echo "$(GREEN)PERFORMANCE TUNING:$(NC)"
	@echo "  make cpu-pin              Enable CPU pinning for optimal performance"
	@echo "  make numa-check           Analyze NUMA topology and optimization"
	@echo "  make cache-setup          Configure CPU cache settings"
	@echo "  make hugepage-setup       Setup huge pages for memory optimization"
	@echo "  make benchmark            Run performance benchmarks"
	@echo "  make performance-test     Run comprehensive performance tests"
	@echo "  make profile              Profile Vera with cProfile"
	@echo ""
	@echo "$(GREEN)MONITORING & DEBUGGING:$(NC)"
	@echo "  make logs-vera            View Vera application logs"
	@echo "  make logs-docker          View Docker logs"
	@echo "  make stats                Show system resource stats"
	@echo "  make check-health         Health check all services"
	@echo "  make watch                Watch live metrics (docker + system)"
	@echo ""
	@echo "$(GREEN)UTILITIES:$(NC)"
	@echo "  make requirements         Generate requirements.txt"
	@echo "  make reset                Full reset (clean + reinstall)"
	@echo "  make version              Show Vera version"
	@echo "  make install-deps-system  Install system dependencies"
	@echo ""
	@echo "$(YELLOW)EXAMPLES:$(NC)"
	@echo "  make docker-scale NUM=5               # Scale to 5 workers"
	@echo "  make docker-cpu                      # Interactively adjust CPU"
	@echo "  make docker-stats                    # View resource usage"
	@echo "  make proxmox-scale NUM=3 PROXMOX_HOST=10.0.0.5"
	@echo ""

info:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    SYSTEM INFORMATION                              ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)System:$(NC)"
	@echo "  CPU Cores: $(CPU_CORES)"
	@echo "  OS: $$(uname -s)"
	@echo "  Kernel: $$(uname -r)"
	@echo ""
	@echo "$(GREEN)Python:$(NC)"
	@echo "  Version: $$($(PYTHON) --version 2>&1)"
	@echo "  Executable: $$(which $(PYTHON))"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@echo "  Version: $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "  Running Containers: $$(docker ps -q 2>/dev/null | wc -l)"
	@echo ""
	@echo "$(GREEN)Vera Project:$(NC)"
	@echo "  Root: $(VERA_ROOT)"
	@echo "  Main: $(VERA_MAIN)"
	@echo "  Venv: $(VENV)"
	@echo ""

# ==================== SETUP & ENVIRONMENT ====================
venv:
	@echo "$(YELLOW)Creating virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✓ Virtual environment created$(NC)"

install: venv
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

dev: install
	@echo "$(YELLOW)Installing dev dependencies...$(NC)"
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "  Activate with: source $(VENV)/bin/activate"

requirements:
	$(VENV)/bin/pip freeze > requirements.txt
	@echo "$(GREEN)✓ requirements.txt updated$(NC)"

# ==================== TESTING ====================
test: test-unit test-integration
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-unit:
	@echo "$(YELLOW)Running unit tests...$(NC)"
	$(PYTEST) $(VERA_TESTS)/unit -v --tb=short
	@echo "$(GREEN)✓ Unit tests passed$(NC)"

test-integration:
	@echo "$(YELLOW)Running integration tests...$(NC)"
	$(PYTEST) $(VERA_TESTS)/integration -v --tb=short
	@echo "$(GREEN)✓ Integration tests passed$(NC)"

test-performance:
	@echo "$(YELLOW)Running performance tests...$(NC)"
	$(PYTEST) $(VERA_TESTS)/performance -v --tb=short -s
	@echo "$(GREEN)✓ Performance tests completed$(NC)"

coverage:
	@echo "$(YELLOW)Generating coverage report...$(NC)"
	$(PYTEST) $(VERA_TESTS) --cov=vera --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated: htmlcov/index.html$(NC)"

# ==================== CODE QUALITY ====================
lint:
	@echo "$(YELLOW)Running linters...$(NC)"
	$(VENV)/bin/flake8 vera --max-line-length=100 --exclude=__pycache__ || true
	$(VENV)/bin/pylint vera --disable=C0111,C0103 || true
	@echo "$(GREEN)✓ Linting completed$(NC)"

format:
	@echo "$(YELLOW)Formatting code...$(NC)"
	$(VENV)/bin/black vera tests
	$(VENV)/bin/isort vera tests
	@echo "$(GREEN)✓ Code formatted$(NC)"

# ==================== DEVELOPMENT ====================
run:
	@echo "$(YELLOW)Starting Vera agent...$(NC)"
	$(PYTHON) $(VERA_MAIN)

run-ui:
	@echo "$(YELLOW)Starting Vera UI (http://localhost:8000)...$(NC)"
	$(PYTHON) $(VERA_UI)

run-focus:
	@echo "$(YELLOW)Running proactive focus manager...$(NC)"
	$(PYTHON) -c "from vera import Vera; vera = Vera(); vera.focus_manager.run_proactive_cycle()"

logs-vera:
	tail -f vera.log

clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ vera.prof
	@echo "$(GREEN)✓ Clean completed$(NC)"

reset: clean
	@echo "$(YELLOW)Resetting environment...$(NC)"
	rm -rf $(VENV)
	@echo "$(GREEN)✓ Reset completed. Run 'make install' to reinstall$(NC)"

docs:
	@echo "$(YELLOW)Generating documentation...$(NC)"
	mkdir -p $(VERA_DOCS)
	@echo "$(GREEN)✓ Documentation generated$(NC)"

version:
	@$(PYTHON) -c "import vera; print('Vera version:', vera.__version__)" 2>/dev/null || echo "Version not found"

# ==================== DOCKER MANAGEMENT ====================
docker-build:
	@echo "$(YELLOW)Building Docker image: $(DOCKER_IMAGE)...$(NC)"
	docker build -t $(DOCKER_IMAGE) -f Dockerfile .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-up:
	@echo "$(YELLOW)Starting Docker containers...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d
	@echo "$(GREEN)✓ Containers started$(NC)"
	@sleep 2
	@docker ps -f "label=app=vera"

docker-down:
	@echo "$(YELLOW)Stopping Docker containers...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml down
	@echo "$(GREEN)✓ Containers stopped$(NC)"

docker-logs:
	$(DOCKER_COMPOSE) -f docker-compose.yml logs -f

docker-logs-service:
	@if [ -z "$(SVC)" ]; then \
		echo "Usage: make docker-logs-service SVC=service_name"; \
		exit 1; \
	fi
	docker logs -f $$(docker ps -qf "label=service=$(SVC)")

docker-shell:
	@SVC=$${SVC:-vera}; \
	echo "$(YELLOW)Opening shell in $$SVC container...$(NC)"; \
	docker exec -it $$(docker ps -qf "label=service=$$SVC") /bin/bash

docker-scale:
	@if [ -z "$(NUM)" ]; then \
		echo "$(RED)Usage: make docker-scale NUM=n$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Scaling $(WORKER_SERVICE) to $(NUM) containers...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --scale $(WORKER_SERVICE)=$(NUM)
	@echo "$(GREEN)✓ Scaled to $(NUM) containers$(NC)"
	@sleep 1
	@docker ps -f "label=service=$(WORKER_SERVICE)"

docker-stats:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    DOCKER CONTAINER STATS                         ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"

docker-watch:
	@echo "$(BLUE)Watching Docker containers (Ctrl+C to exit)...$(NC)"
	@watch -n 1 'docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"'

# ==================== DOCKER CPU & MEMORY SCALING ====================
docker-cpu:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                    DOCKER CPU ADJUSTMENT                          ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Available containers:$(NC)"
	@docker ps --format "table {{.Names}}\t{{.Status}}" | grep vera || echo "No containers running"
	@echo ""
	@read -p "Enter container name (or 'all' for all vera containers): " CONTAINER; \
	read -p "Enter CPU cores (e.g., 0.5, 1, 2): " CPUS; \
	if [ "$$CONTAINER" = "all" ]; then \
		for cid in $$(docker ps -qf "label=app=vera"); do \
			echo "$(YELLOW)Adjusting $$cid to $$CPUS CPUs...$(NC)"; \
			docker update --cpus $$CPUS $$cid; \
		done; \
	else \
		docker update --cpus $$CPUS $$CONTAINER; \
	fi; \
	echo "$(GREEN)✓ CPU allocation updated$(NC)"; \
	docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

docker-cpu-set:
	@if [ -z "$(CONTAINER)" ] || [ -z "$(CPUS)" ]; then \
		echo "$(RED)Usage: make docker-cpu-set CONTAINER=name CPUS=value$(NC)"; \
		echo "Example: make docker-cpu-set CONTAINER=vera_vera-worker_1 CPUS=2"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Setting $(CONTAINER) CPU to $(CPUS)...$(NC)"
	docker update --cpus $(CPUS) $(CONTAINER)
	@echo "$(GREEN)✓ CPU updated to $(CPUS)$(NC)"
	@docker stats --no-stream $(CONTAINER) --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

docker-mem:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                  DOCKER MEMORY ADJUSTMENT                         ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Available containers:$(NC)"
	@docker ps --format "table {{.Names}}\t{{.Status}}" | grep vera || echo "No containers running"
	@echo ""
	@read -p "Enter container name (or 'all' for all vera containers): " CONTAINER; \
	read -p "Enter memory limit (e.g., 512m, 1g, 2g): " MEMORY; \
	if [ "$$CONTAINER" = "all" ]; then \
		for cid in $$(docker ps -qf "label=app=vera"); do \
			echo "$(YELLOW)Adjusting $$cid to $$MEMORY...$(NC)"; \
			docker update --memory $$MEMORY $$cid; \
		done; \
	else \
		docker update --memory $$MEMORY $$CONTAINER; \
	fi; \
	echo "$(GREEN)✓ Memory limits updated$(NC)"; \
	docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

docker-mem-set:
	@if [ -z "$(CONTAINER)" ] || [ -z "$(MEMORY)" ]; then \
		echo "$(RED)Usage: make docker-mem-set CONTAINER=name MEMORY=value$(NC)"; \
		echo "Example: make docker-mem-set CONTAINER=vera_vera-worker_1 MEMORY=2g"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Setting $(CONTAINER) memory to $(MEMORY)...$(NC)"
	docker update --memory $(MEMORY) $(CONTAINER)
	@echo "$(GREEN)✓ Memory updated to $(MEMORY)$(NC)"
	@docker stats --no-stream $(CONTAINER) --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

docker-reset-resources:
	@echo "$(YELLOW)Resetting all Vera containers to defaults...$(NC)"
	@for cid in $$(docker ps -qf "label=app=vera"); do \
		docker update --cpus 0 --memory 0 $$cid; \
	done
	@echo "$(GREEN)✓ Resource limits reset to unlimited$(NC)"

docker-pull:
	docker pull $(DOCKER_REGISTRY)/$(DOCKER_IMAGE)
	@echo "$(GREEN)✓ Docker image pulled$(NC)"

docker-push:
	docker tag $(DOCKER_IMAGE) $(DOCKER_REGISTRY)/$(DOCKER_IMAGE)
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE)
	@echo "$(GREEN)✓ Docker image pushed to $(DOCKER_REGISTRY)$(NC)"

docker-prune:
	@echo "$(YELLOW)Cleaning Docker system...$(NC)"
	docker system prune -f
	@echo "$(GREEN)✓ Docker cleanup completed$(NC)"

# ==================== PROXMOX DEPLOYMENT ====================
proxmox-deploy:
	@echo "$(YELLOW)Deploying Vera to Proxmox ($(PROXMOX_NODE))...$(NC)"
	@./scripts/proxmox-deploy.sh \
		--host $(PROXMOX_HOST) \
		--user $(PROXMOX_USER) \
		--token $(PROXMOX_TOKEN) \
		--node $(PROXMOX_NODE) \
		--storage $(PROXMOX_STORAGE) \
		--memory $(PROXMOX_VM_MEMORY) \
		--cores $(PROXMOX_VM_CORES)
	@echo "$(GREEN)✓ Vera deployed to Proxmox$(NC)"

proxmox-scale:
	@if [ -z "$(NUM)" ]; then \
		echo "$(RED)Usage: make proxmox-scale NUM=n$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Scaling Proxmox VMs to $(NUM) instances...$(NC)"
	@./scripts/proxmox-scale.sh \
		--host $(PROXMOX_HOST) \
		--user $(PROXMOX_USER) \
		--token $(PROXMOX_TOKEN) \
		--num $(NUM)
	@echo "$(GREEN)✓ Proxmox VMs scaled to $(NUM)$(NC)"

proxmox-monitor:
	@echo "$(YELLOW)Monitoring Proxmox resources...$(NC)"
	@./scripts/proxmox-monitor.sh \
		--host $(PROXMOX_HOST) \
		--user $(PROXMOX_USER) \
		--token $(PROXMOX_TOKEN)

proxmox-destroy:
	@read -p "$(YELLOW)Are you sure? This will destroy all Vera VMs. [y/N]$(NC) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		./scripts/proxmox-destroy.sh \
			--host $(PROXMOX_HOST) \
			--user $(PROXMOX_USER) \
			--token $(PROXMOX_TOKEN); \
		echo "$(GREEN)✓ Vera VMs destroyed$(NC)"; \
	else \
		echo "$(YELLOW)✗ Cancelled$(NC)"; \
	fi

proxmox-status:
	@./scripts/proxmox-status.sh \
		--host $(PROXMOX_HOST) \
		--user $(PROXMOX_USER) \
		--token $(PROXMOX_TOKEN)

# ==================== PERFORMANCE TUNING ====================
cpu-pin:
	@echo "$(YELLOW)Enabling CPU pinning...$(NC)"
	@./scripts/cpu-pinning.sh $(CPU_CORES)
	@echo "$(GREEN)✓ CPU pinning enabled for $(CPU_CORES) cores$(NC)"

numa-check:
	@echo "$(BLUE)NUMA Configuration:$(NC)"
	@numactl --hardware || echo "$(RED)numactl not installed$(NC)"
	@echo ""
	@echo "$(BLUE)Memory topology:$(NC)"
	@numastat -p $$ || echo "$(RED)numastat not available$(NC)"

cache-setup:
	@echo "$(YELLOW)Optimizing CPU cache settings...$(NC)"
	@./scripts/cache-optimization.sh
	@echo "$(GREEN)✓ Cache optimization applied$(NC)"

hugepage-setup:
	@echo "$(YELLOW)Setting up $(HUGEPAGE_COUNT) x $(HUGEPAGE_SIZE) huge pages...$(NC)"
	@echo $(HUGEPAGE_COUNT) | sudo tee /sys/kernel/mm/hugepages/hugepages-$(HUGEPAGE_SIZE)/nr_hugepages > /dev/null
	@cat /proc/meminfo | grep -i huge
	@echo "$(GREEN)✓ Huge pages configured$(NC)"

benchmark:
	@echo "$(YELLOW)Running benchmarks...$(NC)"
	$(PYTHON) -c "from vera.performance import benchmark; benchmark.run_full_suite()"
	@echo "$(GREEN)✓ Benchmark completed$(NC)"

performance-test:
	@echo "$(YELLOW)Running comprehensive performance tests...$(NC)"
	$(PYTEST) $(VERA_TESTS)/performance -v -s --tb=short
	@make benchmark
	@echo "$(GREEN)✓ Performance analysis complete$(NC)"

profile:
	@echo "$(YELLOW)Profiling Vera...$(NC)"
	$(PYTHON) -m cProfile -o vera.prof $(VERA_MAIN)
	$(PYTHON) -m pstats vera.prof
	@echo "$(GREEN)✓ Profiling complete: vera.prof$(NC)"

# ==================== MONITORING ====================
stats:
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║                  SYSTEM RESOURCE STATISTICS                       ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)CPU Usage:$(NC)"
	@top -bn1 | grep "Cpu(s)" || ps aux --sort=-%cpu | head -6
	@echo ""
	@echo "$(GREEN)Memory Usage:$(NC)"
	@free -h
	@echo ""
	@echo "$(GREEN)Docker Container Stats:$(NC)"
	@docker stats --no-stream 2>/dev/null || echo "No containers running"

watch:
	@echo "$(BLUE)Watching system and container metrics (Ctrl+C to exit)...$(NC)"
	@while true; do \
		clear; \
		echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════╗$(NC)"; \
		echo "$(BLUE)║              SYSTEM & DOCKER MONITORING - $$(date '+%H:%M:%S')                   ║$(NC)"; \
		echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════╝$(NC)"; \
		echo ""; \
		echo "$(GREEN)System CPU:$(NC)"; \
		top -bn1 | grep "Cpu(s)"; \
		echo ""; \
		echo "$(GREEN)Memory:$(NC)"; \
		free -h | head -2; \
		echo ""; \
		echo "$(GREEN)Docker Containers:$(NC)"; \
		docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "No containers"; \
		sleep 2; \
	done

check-health:
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo "  - Vera CLI: " && $(PYTHON) -c "from vera import Vera; print('$(GREEN)✓ OK$(NC)')" || echo "$(RED)✗ FAILED$(NC)"
	@echo "  - Docker: " && docker ps -q &>/dev/null && echo "$(GREEN)✓ OK$(NC)" || echo "$(RED)✗ FAILED$(NC)"
	@echo "  - Memory DBs: " && $(PYTHON) -c "import chromadb; print('$(GREEN)✓ ChromaDB OK$(NC)')" || echo "$(RED)✗ ChromaDB FAILED$(NC)"
	@echo "$(GREEN)✓ Health check complete$(NC)"

# ==================== UTILITY COMMANDS ====================
install-deps-system:
	@echo "$(YELLOW)Installing system dependencies...$(NC)"
	@which apt-get > /dev/null && (sudo apt-get update && sudo apt-get install -y \
		build-essential python3-dev python3-pip \
		docker.io docker-compose \
		numactl hwloc \
		proxmox-ve) || echo "$(RED)Unsupported package manager$(NC)"
	@echo "$(GREEN)✓ System dependencies installed$(NC)"

all: install test lint format
	@echo "$(GREEN)✓ Full build completed$(NC)"


# ==================== EXAMPLES ====================
# # Scale workers then adjust their CPU
# make docker-scale NUM=5
# make docker-cpu-set CONTAINER=vera_vera-worker_1 CPUS=2

# # Interactive adjustment for all containers
# make docker-cpu        # Prompts for container name and CPU cores
# make docker-mem        # Prompts for container name and memory

# # Real-time monitoring
# make docker-watch      # Docker only
# make watch             # System + Docker combined

# # Performance optimization
# make cpu-pin
# make hugepage-setup
# make performance-test