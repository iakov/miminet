# Makefile для Miminet

.DEFAULT_GOAL := help

# Цвета для вывода
CYAN := \033[0;36m
RESET := \033[0m

.PHONY: help start stop restart logs test clean db-migrate db-upgrade format lint install install-dev install-frontend install-backend install-frontend-dev install-backend-dev shell add add-dev remove

help: ## Показать эту справку
	@echo "$(CYAN)Доступные команды:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'

# ============================================================================
# uv / Управление зависимостями
# ============================================================================

install: ## Установить только core зависимости
	@echo "$(CYAN)Installing core dependencies only...$(RESET)"
	uv sync

install-dev: ## Установить ВСЕ зависимости (фронт + бэк + девтулзы)
	@echo "$(CYAN)Installing all dependencies (frontend + backend + dev)...$(RESET)"
	uv sync --group frontend --group backend --group dev-frontend --group dev-backend --group dev --group prod

install-frontend: ## Установить ТОЛЬКО frontend зависимости
	@echo "$(CYAN)Installing frontend dependencies only...$(RESET)"
	uv sync --group frontend

install-backend: ## Установить ТОЛЬКО backend зависимости
	@echo "$(CYAN)Installing backend dependencies only...$(RESET)"
	uv sync --group backend

install-frontend-dev: ## Установить frontend + фронтенд тесты/девтулзы
	@echo "$(CYAN)Installing frontend + dev tools...$(RESET)"
	uv sync --group frontend --group dev-frontend

install-backend-dev: ## Установить backend + бэкенд тесты/девтулзы
	@echo "$(CYAN)Installing backend + dev tools...$(RESET)"
	uv sync --group backend --group dev-backend

shell: ## Активировать uv venv
	@echo "$(CYAN)Activating uv virtual environment...$(RESET)"
	. .venv/bin/activate

add: ## Добавить новую зависимость (make add PKG=pytest-html)
	@if [ -z "$(PKG)" ]; then \
		echo "Usage: make add PKG=package-name"; \
		exit 1; \
	fi
	uv add $(PKG)

add-dev: ## Добавить dev зависимость (make add-dev PKG=pytest)
	@if [ -z "$(PKG)" ]; then \
		echo "Usage: make add-dev PKG=package-name"; \
		exit 1; \
	fi
	uv add --group dev $(PKG)

remove: ## Удалить зависимость (make remove PKG=pytest-html)
	@if [ -z "$(PKG)" ]; then \
		echo "Usage: make remove PKG=package-name"; \
		exit 1; \
	fi
	uv remove $(PKG)

# ============================================================================
# Управление контейнерами
# ============================================================================

start: ## Запустить все контейнеры
	@echo "$(CYAN)Starting all containers...$(RESET)"
	./start_all_containers.sh

stop: ## Остановить все контейнеры
	@echo "$(CYAN)Stopping all containers...$(RESET)"
	docker-compose -f front/docker-compose.yml down
	docker-compose -f back/docker-compose.yml down

restart: stop start ## Перезапустить все контейнеры

# ============================================================================
# Логи
# ============================================================================

logs: ## Показать логи всех сервисов
	@echo "$(CYAN)Showing logs (Ctrl+C to stop)...$(RESET)"
	docker-compose -f front/docker-compose.yml logs -f & \
	docker-compose -f back/docker-compose.yml logs -f

logs-front: ## Логи frontend
	docker logs -f miminet

logs-back: ## Логи backend
	docker logs -f celery

logs-rabbit: ## Логи RabbitMQ
	docker logs -f rabbitmq

logs-postgres: ## Логи PostgreSQL
	docker logs -f postgres

# ============================================================================
# Тестирование
# ============================================================================

test: install-dev ## Запустить все тесты
	@echo "$(CYAN)Running all tests...$(RESET)"
	@echo "Frontend tests:"
	uv run pytest front/tests -v
	@echo "\nBackend tests (requires sudo):"
	sudo bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && uv run pytest -v"

test-front: ## Тесты frontend (Selenium)
	@echo "$(CYAN)Running frontend tests...$(RESET)"
	uv run pytest front/tests -v

test-back: ## Тесты backend (requires sudo)
	@echo "$(CYAN)Running backend tests...$(RESET)"
	sudo bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && uv run pytest -v"

test-back-cov: ## Тесты backend с coverage (requires sudo)
	@echo "$(CYAN)Running backend tests with coverage...$(RESET)"
	sudo bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && uv run pytest -v \
		--cov=../src \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-report=json"
	@echo "$(CYAN)Coverage report: back/tests/htmlcov/index.html$(RESET)"

test-front-cov: ## Тесты frontend с coverage
	@echo "$(CYAN)Running frontend tests with coverage...$(RESET)"
	uv run pytest front/tests -v \
		--cov=front/src \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-report=json
	@echo "$(CYAN)Coverage report: htmlcov/index.html$(RESET)"

test-coverage: ## Тесты с coverage (all)
	@echo "$(CYAN)Running all tests with coverage...$(RESET)"
	@echo "Frontend:"
	uv run pytest front/tests --cov=front/src --cov-report=term
	@echo "\nBackend (requires sudo):"
	sudo bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && uv run pytest \
		--cov=../src \
		--cov-report=term-missing"

test-back-quick: ## Быстрые тесты backend (без Mininet)
	@echo "$(CYAN)Running quick backend unit tests...$(RESET)"
	bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && \
		uv run pytest test_pkt_parser.py test_network_schema.py -v"

test-selenium: ## Запустить Selenium тесты с HTML отчетом
	@echo "$(CYAN)Running Selenium tests with HTML report...$(RESET)"
	mkdir -p front/tests/screenshots front/tests/videos
	uv run pytest front/tests \
		--html=front/tests/report.html \
		--self-contained-html \
		--tb=short \
		-v
	@echo "$(CYAN)Report: front/tests/report.html$(RESET)"
	@echo "$(CYAN)Screenshots: front/tests/screenshots/$(RESET)"

test-selenium-debug: ## Selenium тесты с отладкой и выводом логов
	@echo "$(CYAN)Running Selenium tests in debug mode...$(RESET)"
	mkdir -p front/tests/screenshots
	uv run pytest front/tests \
		--html=front/tests/report.html \
		--self-contained-html \
		-vv -s \
		--tb=long

test-selenium-report: ## Открыть HTML отчет Selenium тестов
	@echo "$(CYAN)Opening Selenium test report...$(RESET)"
	@if [ -f "front/tests/report.html" ]; then \
		open front/tests/report.html || xdg-open front/tests/report.html || start front/tests/report.html; \
	else \
		echo "Report not found. Run 'make test-selenium' first"; \
	fi

test-screenshots: ## Показать скриншоты ошибок
	@echo "$(CYAN)Selenium test screenshots:$(RESET)"
	@ls -lah front/tests/screenshots/ | grep PNG || echo "No screenshots found"

test-fail: ## Повторить только упавшие тесты
	@echo "$(CYAN)Running failed tests...$(RESET)"
	uv run pytest front/tests --lf -v
	sudo bash -c "cd back/tests && export PYTHONPATH=$$PYTHONPATH:../src && uv run pytest --lf -v"

test-debug: ## Тесты с выводом (show debug info)
	@echo "$(CYAN)Running tests with debug output...$(RESET)"
	uv run pytest front/tests -v -s --tb=short

# ============================================================================
# База данных
# ============================================================================

db-migrate: ## Создать миграцию БД (MSG="описание")
	@if [ -z "$(MSG)" ]; then \
		echo "$(CYAN)Usage: make db-migrate MSG=\"Description of changes\"$(RESET)"; \
		exit 1; \
	fi
	docker exec -it miminet flask db migrate -m "$(MSG)"

db-upgrade: ## Применить миграции
	@echo "$(CYAN)Applying database migrations...$(RESET)"
	docker exec -it miminet flask db upgrade

db-downgrade: ## Откатить последнюю миграцию
	@echo "$(CYAN)Rolling back last migration...$(RESET)"
	docker exec -it miminet flask db downgrade

db-current: ## Показать текущую версию БД
	docker exec -it miminet flask db current

db-history: ## Показать историю миграций
	docker exec -it miminet flask db history

db-reset: ## Пересоздать БД (ОСТОРОЖНО!)
	@echo "$(CYAN)⚠️  WARNING: This will delete all data! Press Ctrl+C to cancel...$(RESET)"
	@sleep 5
	docker exec -it miminet bash -c "rm -rf migrations/ && flask db init && flask db migrate && flask db upgrade"
	@echo "$(CYAN)Database reset complete$(RESET)"

# ============================================================================
# Shell доступ
# ============================================================================

shell-front: ## Shell в frontend контейнере
	docker exec -it miminet bash

shell-back: ## Shell в backend контейнере
	docker exec -it celery bash

shell-db: ## PostgreSQL shell
	docker exec -it postgres psql -U miminet -d miminet

shell-rabbit: ## RabbitMQ shell
	docker exec -it rabbitmq bash

# ============================================================================
# Код quality
# ============================================================================

format: ## Форматировать код (black + isort)
	@echo "$(CYAN)Formatting code...$(RESET)"
	black front/src back/src
	isort front/src back/src
	@echo "$(CYAN)Code formatted$(RESET)"

lint: ## Проверить код (flake8)
	@echo "$(CYAN)Linting code...$(RESET)"
	flake8 front/src back/src --max-line-length=120 --ignore=E203,W503
	@echo "$(CYAN)Linting complete$(RESET)"

lint-fix: format lint ## Форматировать и проверить код

# ============================================================================
# Очистка
# ============================================================================

clean: ## Очистить временные файлы
	@echo "$(CYAN)Cleaning temporary files...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "$(CYAN)Cleanup complete$(RESET)"

clean-all: clean ## Очистить всё (включая Docker volumes)
	@echo "$(CYAN)⚠️  WARNING: This will remove Docker volumes! Press Ctrl+C to cancel...$(RESET)"
	@sleep 5
	docker-compose -f front/docker-compose.yml down -v
	docker-compose -f back/docker-compose.yml down -v
	@echo "$(CYAN)Deep cleanup complete$(RESET)"

# ============================================================================
# RabbitMQ
# ============================================================================

rabbit-queues: ## Показать очереди RabbitMQ
	docker exec -it rabbitmq rabbitmqctl list_queues

rabbit-purge: ## Очистить очередь celery
	docker exec -it rabbitmq rabbitmqctl purge_queue celery

rabbit-ui: ## Открыть RabbitMQ Management UI
	@echo "$(CYAN)Opening RabbitMQ Management UI...$(RESET)"
	@echo "URL: http://localhost:15672"
	@echo "Username: guest"
	@echo "Password: guest"

# ============================================================================
# Development
# ============================================================================

dev-setup: ## Настроить окружение для разработки
	@echo "$(CYAN)Setting up development environment...$(RESET)"
	pip install -r front/requirements.txt
	pip install -r back/requirements.txt
	pip install black isort flake8 pytest pytest-cov
	@echo "$(CYAN)Installing pre-commit hooks...$(RESET)"
	pip install pre-commit
	pre-commit install
	@echo "$(CYAN)Development setup complete$(RESET)"

install-deps: ## Установить зависимости
	@echo "$(CYAN)Installing dependencies...$(RESET)"
	pip install -r front/requirements.txt
	pip install -r back/requirements.txt

check: lint test ## Проверить код и запустить тесты

# ============================================================================
# Docker операции
# ============================================================================

ps: ## Показать статус контейнеров
	@echo "$(CYAN)Container status:$(RESET)"
	docker-compose -f front/docker-compose.yml ps
	docker-compose -f back/docker-compose.yml ps

images: ## Показать образы
	@echo "$(CYAN)Docker images:$(RESET)"
	docker images | grep miminet

build: ## Собрать Docker образы
	@echo "$(CYAN)Building Docker images...$(RESET)"
	docker-compose -f front/docker-compose.yml build
	docker-compose -f back/docker-compose.yml build

pull: ## Обновить базовые образы
	@echo "$(CYAN)Pulling latest images...$(RESET)"
	docker-compose -f front/docker-compose.yml pull
	docker-compose -f back/docker-compose.yml pull

prune: ## Удалить неиспользуемые Docker ресурсы
	@echo "$(CYAN)Pruning Docker resources...$(RESET)"
	docker system prune -f
	docker volume prune -f

# ============================================================================
# Backup / Restore
# ============================================================================

backup-db: ## Создать backup базы данных
	@echo "$(CYAN)Creating database backup...$(RESET)"
	@mkdir -p backups
	docker exec -t postgres pg_dump -U miminet miminet | gzip > backups/backup_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(CYAN)Backup created in backups/ directory$(RESET)"

restore-db: ## Восстановить БД из backup (FILE=path)
	@if [ -z "$(FILE)" ]; then \
		echo "$(CYAN)Usage: make restore-db FILE=backups/backup_YYYYMMDD.sql.gz$(RESET)"; \
		exit 1; \
	fi
	@echo "$(CYAN)⚠️  WARNING: This will overwrite database! Press Ctrl+C to cancel...$(RESET)"
	@sleep 5
	gunzip -c $(FILE) | docker exec -i postgres psql -U miminet -d miminet
	@echo "$(CYAN)Database restored$(RESET)"

# ============================================================================
# Мониторинг
# ============================================================================

stats: ## Показать статистику контейнеров
	docker stats --no-stream

top: ## Показать процессы в контейнерах
	@echo "$(CYAN)Frontend container:$(RESET)"
	docker top miminet
	@echo "\n$(CYAN)Backend container:$(RESET)"
	docker top celery

health: ## Проверить здоровье системы
	@echo "$(CYAN)Checking system health...$(RESET)"
	@echo "Containers:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "miminet|celery|postgres|rabbitmq|redis"
	@echo "\nDisk usage:"
	@docker system df
	@echo "\nRabbitMQ queues:"
	@docker exec -it rabbitmq rabbitmqctl list_queues 2>/dev/null || echo "RabbitMQ not running"

# ============================================================================
# Документация
# ============================================================================

docs: ## Открыть документацию
	@echo "$(CYAN)Available documentation:$(RESET)"
	@echo "  README.md - Project overview"
	@echo "  CLAUDE.md - Claude Code documentation"
	@echo "  CLAUDE_CODE_IMPROVEMENTS.md - Improvement suggestions"
	@echo "  .claude/quick-start.md - Quick start guide"
	@echo "  .claude/common-tasks.md - Common tasks"

# ============================================================================
# CI/CD
# ============================================================================

ci: lint test ## Запустить CI проверки локально
	@echo "$(CYAN)CI checks passed!$(RESET)"

# ============================================================================
# Production
# ============================================================================

prod-start: ## Запустить в production режиме
	@echo "$(CYAN)Starting in production mode...$(RESET)"
	docker-compose -f front/docker-compose-prod.yml up -d
	docker-compose -f back/docker-compose.yml up -d

prod-stop: ## Остановить production
	docker-compose -f front/docker-compose-prod.yml down
	docker-compose -f back/docker-compose.yml down

prod-logs: ## Логи production
	docker-compose -f front/docker-compose-prod.yml logs -f
