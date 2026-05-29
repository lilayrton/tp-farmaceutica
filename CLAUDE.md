# TP Farmacéutica — Contexto del Proyecto

## Descripción

TP universitario para **Ingeniería de Datos II (UADE)**. Sistema de farmacovigilancia con persistencia polyglot: **MongoDB + Neo4j + Redis**, expuesto vía una **API REST con FastAPI**.

Hay dos iteraciones:
- **TP1**: queries standalone por base de datos
- **TP2**: API integrada con patrón Saga para consistencia eventual entre las 3 bases

## Stack Técnico

- **Lenguaje**: Python 3.11+
- **API**: FastAPI + Uvicorn
- **Bases de datos**: MongoDB 7, Neo4j 5, Redis 7 (Alpine)
- **Drivers**: pymongo, neo4j, redis-py, faker
- **Infraestructura**: Docker + Docker Compose

## Comandos Esenciales

```bash
docker compose up -d        # Levantar todos los servicios
make seed                   # Poblar bases de datos (solo primer arranque)
make down                   # Bajar servicios
docker compose down -v      # Reset completo (borra volúmenes)
PYTHONPATH=. python run_demo.py  # Demo completo TP1
```

## URLs de Servicios

| Servicio | URL | Credenciales |
|---|---|---|
| FastAPI | http://localhost:8000 | — |
| Swagger Docs | http://localhost:8000/docs | — |
| Dashboard | http://localhost:8000/dashboard | — |
| Mongo Express | http://localhost:8081 | anónimo |
| Neo4j Browser | http://localhost:7474 | neo4j / farmaceutica |

## Estructura de Directorios

```
api/            # FastAPI: main.py, models.py, saga.py, routers/
mongodb/        # Conexión y queries standalone (a-e)
neo4j_db/       # Conexión y queries standalone (a-e)
redis_db/       # Conexión y queries standalone (a-c)
seed/           # Generador de datos de prueba
static/         # Assets del dashboard web
```

## Las 5 Operaciones de Negocio (TP2)

| Endpoint | Descripción |
|---|---|
| `GET /panel` | Panel de farmacovigilancia (consolida las 3 DBs) |
| `POST /prescripcion/verificar` | Verificación de interacciones antes de prescribir |
| `GET /lote/{numero_lote}/trazabilidad` | Trazabilidad de lote + cadena de frío |
| `GET /medicamento/{medicamento_id}/interacciones` | Análisis de interacciones del medicamento |
| `POST /alerta/cerrar` | Cierre y confirmación de alertas |

## Arquitectura Polyglot

| Base | Rol | Datos |
|---|---|---|
| **MongoDB** | Fuente de verdad histórica | Medicamentos, lotes, distribuidores, ensayos clínicos, efectos adversos |
| **Neo4j** | Motor de relaciones y grafos | Interacciones entre fármacos, redes de principios activos |
| **Redis** | Estado operacional en tiempo real | Alertas, cadena de frío (STREAM), colas, control de acceso |

**Patrón Saga** (`api/saga.py`): orquesta transacciones distribuidas con compensating transactions en LIFO ante fallos — garantiza consistencia eventual sin transacciones globales.

## Variables de Entorno

Definidas en `docker-compose.yml`:
- `MONGO_URI` = `mongodb://mongodb:27017/farmaceutica_tp`
- `NEO4J_URI` = `bolt://neo4j:7687`
- `NEO4J_USER` / `NEO4J_PASSWORD` = `neo4j` / `farmaceutica`
- `REDIS_HOST` / `REDIS_PORT` = `redis` / `6379`
