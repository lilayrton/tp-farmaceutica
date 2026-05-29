"""
API REST — Capa Poliglota (TP2)
Integra MongoDB + Neo4j + Redis en 5 operaciones de negocio.

Ejecutar:
    PYTHONPATH=. uvicorn api.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from mongodb.connection import get_db
from neo4j_db.connection import get_driver
from redis_db.connection import get_redis

from api.routers import op1_panel, op2_prescripcion, op3_trazabilidad, op4_interacciones, op5_cierre_alerta


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verificar conectividad al arrancar
    errors = []
    try:
        get_db().command("ping")
    except Exception as e:
        errors.append(f"MongoDB: {e}")

    try:
        get_driver().verify_connectivity()
    except Exception as e:
        errors.append(f"Neo4j: {e}")

    try:
        get_redis().ping()
    except Exception as e:
        errors.append(f"Redis: {e}")

    if errors:
        print(f"[WARN] Motores no disponibles al arrancar: {'; '.join(errors)}")
    else:
        print("[OK] Conexión verificada a MongoDB, Neo4j y Redis")

    yield


app = FastAPI(
    title="TP Farmaceutica — API Poliglota",
    description=(
        "Capa de persistencia poliglota (MongoDB + Neo4j + Redis) "
        "para el sistema de farmacovigilancia. TP2 — Ingeniería de Datos II."
    ),
    version="2",
    lifespan=lifespan,
)

app.include_router(op1_panel.router, tags=["OP-1 Panel"])
app.include_router(op2_prescripcion.router, tags=["OP-2 Prescripción"])
app.include_router(op3_trazabilidad.router, tags=["OP-3 Trazabilidad"])
app.include_router(op4_interacciones.router, tags=["OP-4 Interacciones"])
app.include_router(op5_cierre_alerta.router, tags=["OP-5 Cierre de Alerta"])

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/dashboard", tags=["Dashboard"])
def get_dashboard():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/", tags=["Info"])
def root():
    return {
        "sistema": "TP Farmacéutica — Persistencia Poliglota",
        "motores": ["MongoDB", "Neo4j", "Redis"],
        "operaciones": {
            "OP-1 Panel de farmacovigilancia": "GET /panel",
            "OP-2 Verificación de prescripción": "POST /prescripcion/verificar",
            "OP-3 Trazabilidad de lote": "GET /lote/{numero_lote}/trazabilidad",
            "OP-4 Análisis de interacciones": "GET /medicamento/{medicamento_id}/interacciones",
            "OP-5 Cierre de alerta": "POST /alerta/cerrar",
        },
        "docs": "/docs",
    }
