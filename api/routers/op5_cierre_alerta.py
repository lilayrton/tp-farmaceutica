"""
OP-5 — Cierre de alerta de farmacovigilancia (3 motores)

Redis   → elimina la alerta del SORTED SET; DECR del contador si es falso positivo
MongoDB → persiste el dictamen completo (resolución + acciones + investigador)
Neo4j   → si se confirma nueva interacción, crea/actualiza la relación INTERACTUA_CON
"""
from datetime import datetime, timezone

from fastapi import APIRouter
from bson import ObjectId

from mongodb.connection import get_db
from neo4j_db.connection import get_driver
from redis_db.connection import get_redis
from redis_db.queries.a_alertas_farmacovigilancia import eliminar_alerta
from api.models import CerrarAlertaRequest

router = APIRouter()


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


def _neo4j_crear_interaccion(pa1: str, pa2: str, tipo: str, severidad: str, mecanismo: str) -> dict:
    driver = get_driver()
    cypher = """
    MATCH (pa1:PrincipioActivo {nombre: $pa1})
    MATCH (pa2:PrincipioActivo {nombre: $pa2})
    MERGE (pa1)-[i:INTERACTUA_CON {tipo: $tipo}]-(pa2)
    ON CREATE SET i.severidad = $severidad,
                  i.mecanismo = $mecanismo,
                  i.confirmada_en = $fecha
    ON MATCH  SET i.severidad = $severidad,
                  i.mecanismo = $mecanismo,
                  i.ultima_confirmacion = $fecha
    RETURN pa1.nombre AS pa1, pa2.nombre AS pa2, i.tipo AS tipo,
           i.severidad AS severidad, i.mecanismo AS mecanismo
    """
    with driver.session() as session:
        result = session.run(
            cypher,
            pa1=pa1, pa2=pa2, tipo=tipo, severidad=severidad,
            mecanismo=mecanismo,
            fecha=datetime.now(timezone.utc).isoformat(),
        )
        row = result.single()
        return row.data() if row else {"error": "Principios activos no encontrados en el grafo"}


@router.post("/alerta/cerrar", summary="Cierre de alerta de farmacovigilancia (3 motores)")
def cerrar_alerta(req: CerrarAlertaRequest):
    """
    **OP-5** — El médico evaluador resuelve una alerta y el sistema actualiza los tres motores:

    1. **Redis** — elimina la alerta del SORTED SET. Si el resultado es `falso_positivo`,
       decrementa el contador del medicamento en las últimas 24h.
    2. **MongoDB** — persiste el dictamen completo (resolución, acciones tomadas, investigador).
    3. **Neo4j** — si se confirma una nueva interacción (`resultado == "confirmado"` y se
       provee `nueva_interaccion`), crea o actualiza la relación `INTERACTUA_CON` en el grafo.

    **Estrategia ante fallos parciales**: cada motor se actualiza en bloque try/except
    independiente. Los errores se registran en el campo `errores` sin interrumpir los demás.
    """
    errores = {}
    redis_data = {}
    mongo_data = {}
    neo4j_data = {}

    # 1. Redis — eliminar alerta y opcionalmente decrementar contador
    try:
        r = get_redis()
        eliminada = eliminar_alerta(r, req.alerta_id)
        redis_data["alerta_eliminada"] = eliminada

        if req.resultado == "falso_positivo":
            from redis_db.queries.c_control_acceso import _contador_key
            key = _contador_key(req.medicamento_id)
            if r.exists(key):
                nuevo_valor = r.decr(key)
                nuevo_valor = max(0, nuevo_valor)
                r.set(key, nuevo_valor)
                redis_data["contador_decrementado"] = True
                redis_data["contador_actual"] = nuevo_valor
            else:
                redis_data["contador_decrementado"] = False
    except Exception as e:
        errores["redis"] = str(e)

    # 2. MongoDB — persistir dictamen
    try:
        mongo_data = _mongo_persistir_dictamen(req)
    except Exception as e:
        errores["mongodb"] = str(e)

    # 3. Neo4j — crear/actualizar interacción si se confirma
    if req.resultado == "confirmado" and req.nueva_interaccion:
        try:
            ni = req.nueva_interaccion
            neo4j_data = _neo4j_crear_interaccion(
                ni.pa1, ni.pa2, ni.tipo, ni.severidad, ni.mecanismo
            )
        except Exception as e:
            errores["neo4j"] = str(e)
    else:
        neo4j_data = {
            "accion": "omitido",
            "motivo": (
                "Resultado es falso positivo — no se modifica el grafo"
                if req.resultado == "falso_positivo"
                else "No se proveyó información de nueva interacción"
            ),
        }

    response = {
        "operacion": "OP-5 Cierre de alerta de farmacovigilancia",
        "motores": ["Redis", "MongoDB", "Neo4j"],
        "alerta_id": req.alerta_id,
        "resultado": req.resultado,
        "redis": redis_data,
        "mongodb": mongo_data,
        "neo4j": neo4j_data,
    }
    if errores:
        response["errores"] = errores
    return response
