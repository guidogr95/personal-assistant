# Production deployment commands for the Telegram Assistant
# Always run from the project root directory.

COMPOSE := docker compose --env-file .env -f deploy/docker-compose.yml

.PHONY: deploy down logs botlogs test

deploy:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

botlogs:
	$(COMPOSE) logs -f bot

test:
	uv run pytest tests/ -q
