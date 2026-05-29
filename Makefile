.PHONY: seed up down

up:
	docker compose up -d

seed:
	docker compose exec api python seed/generar_datos.py --all --redis-load

down:
	docker compose down
