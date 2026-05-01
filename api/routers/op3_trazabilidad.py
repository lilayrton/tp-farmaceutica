"""
OP-3 — Trazabilidad de lote y alerta de ruptura de cadena de frío (2 motores)

Redis   → detecta ruptura en el STREAM de temperatura; publica alerta en SORTED SET
MongoDB → trazabilidad completa del lote (producción → distribuidores actuales)

Neo4j no participa: la trazabilidad es lineal (cadena de custodia embebida en el
documento de lote en MongoDB). El grafo de interacciones no aporta información
relevante sobre dónde está físicamente un lote.
"""
from fastapi import APIRouter, Query

from mongodb.connection import get_db
from redis_db.connection import get_redis
from redis_db.queries.b_cadena_frio import detectar_ruptura_cadena_frio, consultar_tendencia
from mongodb.queries.a_trazabilidad import trazabilidad_lote

router = APIRouter()


@router.get(
    "/lote/{numero_lote}/trazabilidad",
    summary="Trazabilidad de lote + detección de ruptura de cadena de frío (2 motores)",
)
def trazabilidad_y_cadena_frio(
    numero_lote: str,
    vehiculo_id: str = Query(
        default="VEH001",
        description="ID del vehículo refrigerado asociado al lote para verificar temperatura",
    ),
):
    """
    **OP-3** — Cuando se detecta o sospecha una ruptura de cadena de frío:

    - **Redis** lee las últimas lecturas del vehículo desde el STREAM y detecta
      si hubo ruptura (2 lecturas consecutivas fuera del rango 2–8°C). Si hay
      ruptura, publica automáticamente una alerta en el SORTED SET de farmacovigilancia.
    - **MongoDB** recupera la trazabilidad completa del lote: planta de producción,
      historial de distribución y estado actual del stock.

    **¿Por qué Neo4j no participa?**
    La cadena de custodia de un lote es un grafo lineal (DAG de distribución)
    ya embebido en el documento MongoDB. No requiere traversía de grafo compleja;
    el $match sobre `numero_lote` con índice único es O(1).
    """
    errores = {}
    redis_data = {}
    mongo_data = {}

    # 1. Redis — verificar cadena de frío
    try:
        r = get_redis()
        ruptura = detectar_ruptura_cadena_frio(r, vehiculo_id)
        tendencia = consultar_tendencia(r, vehiculo_id)
        redis_data = {
            "vehiculo_id": vehiculo_id,
            "ruptura_detectada": ruptura["ruptura_detectada"],
            "mensaje": ruptura.get("mensaje", "Sin rupturas detectadas"),
            "alerta_publicada": ruptura.get("alerta_publicada"),
            "tendencia_ultimas_12_lecturas": tendencia,
        }
    except Exception as e:
        errores["redis"] = str(e)

    # 2. MongoDB — trazabilidad del lote
    try:
        resultado = trazabilidad_lote(numero_lote)
        if resultado is None:
            mongo_data = {"error": f"Lote '{numero_lote}' no encontrado"}
        else:
            from bson import json_util
            import json
            mongo_data = json.loads(json_util.dumps(resultado))
    except Exception as e:
        errores["mongodb"] = str(e)

    response = {
        "operacion": "OP-3 Trazabilidad de lote y alerta de ruptura de cadena de frío",
        "motores": ["Redis", "MongoDB"],
        "numero_lote": numero_lote,
        "redis": redis_data,
        "mongodb": mongo_data,
    }
    if errores:
        response["errores"] = errores
    return response
