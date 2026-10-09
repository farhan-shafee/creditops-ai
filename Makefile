.PHONY: dev test lint seed eval reset-demo docker-up docker-down mcp

dev:
	pnpm dev

test:
	pnpm test

lint:
	pnpm lint
	pnpm typecheck

seed:
	node scripts/python.mjs scripts/seed.py

eval:
	node scripts/python.mjs scripts/evaluate.py

reset-demo:
	node scripts/python.mjs scripts/reset_demo.py

docker-up:
	docker compose -f infra/docker/compose.yml up -d --build

docker-down:
	docker compose -f infra/docker/compose.yml down

mcp:
	node scripts/python.mjs -m creditops_mcp.server
