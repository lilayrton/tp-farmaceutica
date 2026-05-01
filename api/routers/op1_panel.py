"""
OP-1 — Panel de farmacovigilancia en tiempo real (3 motores)

Redis   → top 5 alertas activas, tamaño de cola, medicamentos con contador elevado
MongoDB → medicamentos con más reportes de efectos adversos en el último mes
Neo4j   → principios activos con mayor número de interacciones graves/contraindicadas
"""
from datetime import datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from mongodb.connection import get_db
from neo4j_db.connection import get_driver
from redis_db.connection import get_redis
from redis_db.queries.a_alertas_farmacovigilancia import listar_alertas_activas
from redis_db.queries.c_control_acceso import tamanio_cola, obtener_contadores_elevados

router = APIRouter()


def _mongo_reportes_ultimo_mes() -> list:
    db = get_db()
    un_mes_atras = datetime.utcnow() - timedelta(days=30)
    pipeline = [
        {"$match": {"fecha": {"$gte": un_mes_atras}}},
        {"$group": {"_id": "$medicamento_id", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
        {
            "$lookup": {
                "from": "medicamentos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "med",
            }
        },
        {
            "$project": {
                "_id": 0,
                "medicamento": {"$arrayElemAt": ["$med.nombre_comercial", 0]},
                "medicamento_id": {"$toString": "$_id"},
                "total_reportes": "$total",
            }
        },
    ]
    return list(db.efectos_adversos.aggregate(pipeline))


def _neo4j_pa_peligrosos(top: int = 5) -> list:
    driver = get_driver()
    cypher = """
    MATCH (pa:PrincipioActivo)-[i:INTERACTUA_CON]-(:PrincipioActivo)
    WHERE i.severidad IN ['grave', 'contraindicada']
    WITH pa, count(i) AS total_interacciones_peligrosas
    RETURN pa.nombre AS principio_activo,
           pa.familia_quimica AS familia,
           total_interacciones_peligrosas
    ORDER BY total_interacciones_peligrosas DESC
    LIMIT $top
    """
    with driver.session() as session:
        result = session.run(cypher, top=top)
        return [r.data() for r in result]


@router.get("/panel", summary="Panel de farmacovigilancia en tiempo real (3 motores)")
def panel_farmacovigilancia():
    """
    **OP-1** — Consolida el estado de riesgo del sistema usando los tres motores:

    - **Redis**: top 5 alertas activas por severidad, tamaño de la cola de evaluación,
      medicamentos con contador elevado en las últimas 24h.
    - **MongoDB**: medicamentos con mayor cantidad de reportes en el último mes.
    - **Neo4j**: principios activos con mayor número de interacciones graves o contraindicadas.
    """
    errores = {}
    redis_data = {}
    mongo_data = {}
    neo4j_data = {}

    try:
        r = get_redis()
        alertas = listar_alertas_activas(r)[:5]
        cola_size = tamanio_cola(r)
        contadores_elevados = obtener_contadores_elevados(r, umbral=5)
        redis_data = {
            "top_alertas_activas": alertas,
            "reportes_pendientes_evaluacion": cola_size,
            "medicamentos_con_contador_elevado_24h": contadores_elevados,
        }
    except Exception as e:
        errores["redis"] = str(e)

    try:
        mongo_data = {
            "medicamentos_mas_reportados_ultimo_mes": _mongo_reportes_ultimo_mes()
        }
    except Exception as e:
        errores["mongodb"] = str(e)

    try:
        neo4j_data = {
            "principios_activos_mas_peligrosos": _neo4j_pa_peligrosos()
        }
    except Exception as e:
        errores["neo4j"] = str(e)

    response = {
        "operacion": "OP-1 Panel de farmacovigilancia en tiempo real",
        "motores": ["Redis", "MongoDB", "Neo4j"],
        "redis": redis_data,
        "mongodb": mongo_data,
        "neo4j": neo4j_data,
    }
    if errores:
        response["errores"] = errores

    return response
