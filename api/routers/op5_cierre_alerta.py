"""
OP-5 — Cierre de alerta de farmacovigilancia (3 motores)

Redis   → consume la alerta de mayor score con ZPOPMAX. DECR del contador si es falso positivo
MongoDB → persiste el dictamen completo (resolución + acciones + investigador)
Neo4j   → si se confirma nueva interacción, crea/actualiza la relación INTERACTUA_CON

Atomicidad: implementada con patrón Saga Orquestada. Si cualquier paso falla,
se ejecutan las transacciones compensatorias en orden inverso sobre los pasos ya
completados — evitando que el sistema quede en estado parcialmente inconsistente.

Ejemplo crítico: ZPOPMAX elimina la alerta de Redis antes de persistir en MongoDB.
Sin Saga, un fallo de MongoDB deja la alerta perdida sin rastro. Con Saga, se
re-inserta (ZADD) con su score original como compensación.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from bson import ObjectId

from mongodb.connection import get_db
from neo4j_db.connection import get_driver
from redis_db.connection import get_redis
from redis_db.queries.a_alertas_farmacovigilancia import (
    consumir_alerta_maxima,
    KEY as REDIS_ALERTAS_KEY,
)
from redis_db.queries.c_control_acceso import _contador_key
from api.models import CerrarAlertaRequest
from api.saga import SagaOrchestrator

router = APIRouter()


# ── Acciones ──────────────────────────────────────────────────────────────────

def _redis_consumir_alerta() -> dict | None:
    return consumir_alerta_maxima(get_redis())


def _redis_decrementar_contador(medicamento_id: str) -> dict:
    r = get_redis()
    key = _contador_key(medicamento_id)
    if r.exists(key):
        nuevo_valor = max(0, r.decr(key))
        r.set(key, nuevo_valor)
        return {"key": key, "decrementado": True, "valor": nuevo_valor}
    return {"key": key, "decrementado": False}


def _mongo_persistir_dictamen(req: CerrarAlertaRequest) -> dict:
    db = get_db()
    dictamen = {
        "alerta_id": req.alerta_id,
        "medicamento_id": req.medicamento_id,
        "resultado": req.resultado,
        "investigador_responsable": req.investigador_id,
        "acciones_tomadas": req.acciones_tomadas,
        "fecha_cierre": datetime.now(timezone.utc),
        "nueva_interaccion_confirmada": req.nueva_interaccion is not None and req.resultado == "confirmado",
    }
    result = db.dictamenes_alertas.insert_one(dictamen)
    return {"dictamen_id": str(result.inserted_id), "persistido": True}


# ── Compensaciones ────────────────────────────────────────────────────────────

def _compensar_restaurar_alerta(alerta: dict | None) -> None:
    """Re-inserta la alerta en el sorted set con su score original."""
    if alerta is None:
        return
    score = alerta.get("score_consumido", alerta.get("score", 1.0))
    original = {k: v for k, v in alerta.items() if k != "score_consumido"}
    get_redis().zadd(REDIS_ALERTAS_KEY, {json.dumps(original): score})


def _compensar_restaurar_contador(contador_info: dict) -> None:
    """Incrementa el contador si fue decrementado en este paso."""
    if not contador_info.get("decrementado"):
        return
    get_redis().incr(contador_info["key"])


def _compensar_borrar_dictamen(dictamen_result: dict) -> None:
    """Elimina el dictamen insertado en MongoDB."""
    dictamen_id = dictamen_result.get("dictamen_id")
    if not dictamen_id:
        return
    get_db().dictamenes_alertas.delete_one({"_id": ObjectId(dictamen_id)})


def _compensar_borrar_interaccion(pa1: str, pa2: str, tipo: str, creada_nueva: bool) -> None:
    """
    Elimina la relación INTERACTUA_CON solo si fue creada en este paso.
    Si la relación ya existía (ON MATCH), no se toca para preservar el estado previo.
    """
    if not creada_nueva:
        return
    driver = get_driver()
    cypher = """
    MATCH (pa1:PrincipioActivo {nombre: $pa1})-[i:INTERACTUA_CON {tipo: $tipo}]-(pa2:PrincipioActivo {nombre: $pa2})
    DELETE i
    """
    with driver.session() as session:
        session.run(cypher, pa1=pa1, pa2=pa2, tipo=tipo)


# ── Router ────────────────────────────────────────────────────────────────────

@router.post("/alerta/cerrar", summary="Cierre de alerta de farmacovigilancia (3 motores)")
def cerrar_alerta(req: CerrarAlertaRequest):
    """
    **OP-5** — El médico evaluador resuelve una alerta y el sistema actualiza los tres motores.

    Atomicidad garantizada mediante **patrón Saga Orquestada**: si cualquier paso falla,
    se ejecutan transacciones compensatorias en orden inverso (LIFO) sobre los pasos ya completados.

    1. **Redis** — consume la alerta de mayor score (ZPOPMAX). Si `falso_positivo`, decrementa contador.
    2. **MongoDB** — persiste el dictamen completo (resolución, acciones, investigador).
    3. **Neo4j** — si `resultado == "confirmado"` y se provee `nueva_interaccion`, crea/actualiza
       la relación `INTERACTUA_CON` en el grafo.
    """
    saga = SagaOrchestrator()

    try:
        # ── Paso 1: Redis — consumir alerta ─────────────────────────────────
        alerta_consumida = _redis_consumir_alerta()
        saga.register(_compensar_restaurar_alerta, alerta_consumida)

        contador_info = {"decrementado": False}
        if req.resultado == "falso_positivo":
            contador_info = _redis_decrementar_contador(req.medicamento_id)
            saga.register(_compensar_restaurar_contador, contador_info)

        # ── Paso 2: MongoDB — persistir dictamen ────────────────────────────
        dictamen_result = _mongo_persistir_dictamen(req)
        saga.register(_compensar_borrar_dictamen, dictamen_result)

        # ── Paso 3: Neo4j — crear interacción si se confirma ────────────────
        neo4j_data = {
            "accion": "omitido",
            "motivo": (
                "Resultado es falso positivo — no se modifica el grafo"
                if req.resultado == "falso_positivo"
                else "No se proveyó información de nueva interacción"
            ),
        }
        if req.resultado == "confirmado" and req.nueva_interaccion:
            ni = req.nueva_interaccion
            # Capturamos creada_nueva antes de llamar a la función para la compensación
            _raw = _neo4j_crear_interaccion_raw(ni.pa1, ni.pa2, ni.tipo, ni.severidad, ni.mecanismo)
            neo4j_creada_nueva = _raw.pop("creada_nueva", False)
            neo4j_data = _raw
            saga.register(_compensar_borrar_interaccion, ni.pa1, ni.pa2, ni.tipo, neo4j_creada_nueva)

        return {
            "operacion": "OP-5 Cierre de alerta de farmacovigilancia",
            "motores": ["Redis", "MongoDB", "Neo4j"],
            "alerta_id": req.alerta_id,
            "resultado": req.resultado,
            "redis": {
                "alerta_consumida": alerta_consumida,
                **({"contador_decrementado": contador_info.get("decrementado"),
                    "contador_actual": contador_info.get("valor")}
                   if req.resultado == "falso_positivo" else {}),
            },
            "mongodb": dictamen_result,
            "neo4j": neo4j_data,
        }

    except Exception as exc:
        compensation_errors = saga.compensate_all()
        response = {
            "operacion": "OP-5 Cierre de alerta de farmacovigilancia",
            "motores": ["Redis", "MongoDB", "Neo4j"],
            "alerta_id": req.alerta_id,
            "resultado": req.resultado,
            "error": str(exc),
            "saga": "compensación ejecutada — pasos previos revertidos",
        }
        if compensation_errors:
            response["errores_compensacion"] = compensation_errors
        return response


def _neo4j_crear_interaccion_raw(pa1: str, pa2: str, tipo: str, severidad: str, mecanismo: str) -> dict:
    """Versión interna que devuelve creada_nueva para la lógica de compensación."""
    driver = get_driver()
    cypher = """
    MATCH (pa1:PrincipioActivo {nombre: $pa1})
    MATCH (pa2:PrincipioActivo {nombre: $pa2})
    MERGE (pa1)-[i:INTERACTUA_CON {tipo: $tipo}]-(pa2)
    ON CREATE SET i.severidad = $severidad,
                  i.mecanismo = $mecanismo,
                  i.confirmada_en = $fecha,
                  i._saga_created = true
    ON MATCH  SET i.severidad = $severidad,
                  i.mecanismo = $mecanismo,
                  i.ultima_confirmacion = $fecha,
                  i._saga_created = false
    RETURN pa1.nombre AS pa1, pa2.nombre AS pa2, i.tipo AS tipo,
           i.severidad AS severidad, i.mecanismo AS mecanismo,
           i._saga_created AS creada_nueva
    """
    with driver.session() as session:
        result = session.run(
            cypher,
            pa1=pa1, pa2=pa2, tipo=tipo, severidad=severidad,
            mecanismo=mecanismo,
            fecha=datetime.now(timezone.utc).isoformat(),
        )
        row = result.single()
        if not row:
            return {"error": "Principios activos no encontrados en el grafo", "creada_nueva": False}
        return row.data()
