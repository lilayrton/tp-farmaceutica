"""
OP-2 — Verificación de prescripción y detección de riesgos (3 motores)

Orden de consultas:
  0. MongoDB  → principios activos del medicamento a prescribir (paso previo)
  1. Neo4j    → interacciones entre los PAs del nuevo medicamento y los meds actuales del paciente
  2. Redis    → alertas activas sobre el medicamento a prescribir
  3. MongoDB  → historial de efectos adversos de medicamentos del mismo grupo farmacológico
  4. Redis    → si hay interacción grave, escalar/publicar alerta de alta severidad
"""
from datetime import datetime, timedelta

from fastapi import APIRouter
from bson import ObjectId

from mongodb.connection import get_db
from neo4j_db.connection import get_driver
from redis_db.connection import get_redis
from redis_db.queries.a_alertas_farmacovigilancia import (
    listar_alertas_activas,
    publicar_alerta,
)
from api.models import VerificarPrescripcionRequest

router = APIRouter()


def _mongo_pa_del_medicamento(medicamento_id: str) -> dict:
    """Recupera nombres e IDs de principios activos del medicamento a prescribir."""
    db = get_db()
    try:
        med_oid = ObjectId(medicamento_id)
    except Exception:
        return {"error": f"ID de medicamento inválido: {medicamento_id}", "nombres": [], "ids": []}

    med = db.medicamentos.find_one({"_id": med_oid})
    if not med:
        return {"error": f"Medicamento '{medicamento_id}' no encontrado", "nombres": [], "ids": []}

    pa_ids_raw = med.get("principios_activos", [])
    nombres_pa = []
    pa_oids = []
    for pa_ref in pa_ids_raw:
        pa_id = pa_ref.get("id") if isinstance(pa_ref, dict) else pa_ref
        if pa_id:
            pa_oid = ObjectId(str(pa_id))
            pa_oids.append(pa_oid)
            pa_doc = db.principios_activos.find_one({"_id": pa_oid})
            if pa_doc:
                nombres_pa.append(pa_doc["nombre"])

    return {
        "nombre_comercial": med.get("nombre_comercial"),
        "nombres": nombres_pa,
        "ids": pa_oids,
    }


def _neo4j_interacciones_prescripcion(paciente_id: str, pa_del_nuevo: list[str]) -> list:
    """
    Detecta interacciones entre los PAs del medicamento a prescribir
    y los PAs de los medicamentos que el paciente ya toma.
    """
    if not pa_del_nuevo:
        return []
    driver = get_driver()
    cypher = """
    MATCH (pac:Paciente {id_anonimo: $paciente_id})
          -[:TOMA]->(m:Medicamento)-[:CONTIENE]->(pa_existente:PrincipioActivo)
    WITH collect(DISTINCT pa_existente) AS pa_actuales
    UNWIND $pa_del_nuevo AS nombre_nuevo
    MATCH (pa_nuevo:PrincipioActivo {nombre: nombre_nuevo})
    UNWIND pa_actuales AS pa_existente
    MATCH (pa_nuevo)-[i:INTERACTUA_CON]-(pa_existente)
    RETURN pa_nuevo.nombre    AS pa_nuevo,
           pa_existente.nombre AS pa_existente,
           i.tipo             AS tipo_interaccion,
           i.severidad        AS severidad,
           i.mecanismo        AS mecanismo
    ORDER BY
      CASE i.severidad
        WHEN 'contraindicada' THEN 1
        WHEN 'grave'          THEN 2
        WHEN 'moderada'       THEN 3
        ELSE 4
      END
    """
    with driver.session() as session:
        result = session.run(cypher, paciente_id=paciente_id, pa_del_nuevo=pa_del_nuevo)
        return [r.data() for r in result]


def _mongo_historial_efectos_grupo(pa_oids: list) -> list:
    """
    Recupera efectos adversos de medicamentos del mismo grupo farmacológico
    (comparten al menos un principio activo con el medicamento a prescribir).
    """
    db = get_db()
    seis_meses = datetime.utcnow() - timedelta(days=180)

    if not pa_oids:
        return []

    # 1. Medicamentos que comparten al menos un PA con el medicamento a prescribir
    meds_mismo_grupo = list(db.medicamentos.find(
        {"principios_activos": {"$elemMatch": {"$in": pa_oids}}},
        {"_id": 1}
    ))
    med_ids = [m["_id"] for m in meds_mismo_grupo]

    if not med_ids:
        return []

    # 2. Efectos adversos de ese grupo en los últimos 6 meses
    pipeline = [
        {"$match": {
            "medicamento_id": {"$in": med_ids},
            "fecha": {"$gte": seis_meses},
        }},
        {"$sort": {"fecha": -1}},
        {"$limit": 10},
        {"$project": {
            "_id": 0,
            "efecto": "$termino_meddra",
            "gravedad": 1,
            "pais": "$pais_reporte",
            "fecha": 1,
        }},
    ]
    return list(db.efectos_adversos.aggregate(pipeline))


@router.post("/prescripcion/verificar", summary="Verificar prescripción y detectar riesgos (3 motores)")
def verificar_prescripcion(req: VerificarPrescripcionRequest):
    """
    **OP-2** — Antes de prescribir un medicamento, verifica riesgos en tiempo real:

    0. **MongoDB** (paso previo) recupera los principios activos del medicamento a prescribir.
    1. **Neo4j** detecta interacciones entre los PAs del nuevo medicamento y los meds del paciente.
    2. **Redis** consulta alertas activas sobre el medicamento a prescribir.
    3. **MongoDB** recupera efectos adversos de medicamentos del mismo grupo farmacológico.
    4. **Redis** publica alerta de alta severidad si hay interacción grave o contraindicada.
    """
    errores = {}
    interacciones = []
    alertas_activas = []
    historial_ea = []
    alerta_generada = None
    pa_info = {"nombres": [], "ids": []}

    # 0. MongoDB — principios activos del medicamento a prescribir (paso previo)
    try:
        pa_info = _mongo_pa_del_medicamento(req.medicamento_id)
        if "error" in pa_info:
            errores["mongodb_pa"] = pa_info["error"]
    except Exception as e:
        errores["mongodb_pa"] = str(e)

    # 1. Neo4j — interacciones del nuevo medicamento con los del paciente
    try:
        interacciones = _neo4j_interacciones_prescripcion(
            req.paciente_id, pa_info.get("nombres", [])
        )
    except Exception as e:
        errores["neo4j"] = str(e)

    # 2. Redis — alertas activas sobre el medicamento a prescribir
    try:
        r = get_redis()
        todas = listar_alertas_activas(r)
        alertas_activas = [a for a in todas if a.get("medicamento_id") == req.medicamento_id]
    except Exception as e:
        errores["redis_lectura"] = str(e)

    # 3. MongoDB — historial de efectos adversos del grupo farmacológico
    try:
        historial_ea = _mongo_historial_efectos_grupo(pa_info.get("ids", []))
    except Exception as e:
        errores["mongodb_historial"] = str(e)

    # 4. Redis — escalar/publicar alerta si hay interacción grave o contraindicada
    hay_grave = any(
        i.get("severidad") in ("grave", "contraindicada") for i in interacciones
    )
    if hay_grave:
        try:
            r = get_redis()
            alerta_generada = publicar_alerta(
                r,
                medicamento_id=req.medicamento_id,
                severidad=5,
                tipo="interaccion_grave",
                descripcion=(
                    f"Interacción grave detectada al prescribir {req.medicamento_id} "
                    f"a paciente {req.paciente_id}"
                ),
            )
        except Exception as e:
            errores["redis_publicacion"] = str(e)

    response = {
        "operacion": "OP-2 Verificación de prescripción",
        "motores": ["Neo4j", "Redis", "MongoDB"],
        "paciente_id": req.paciente_id,
        "medicamento_id": req.medicamento_id,
        "medicamento": pa_info.get("nombre_comercial"),
        "neo4j": {
            "interacciones_detectadas": interacciones,
            "total": len(interacciones),
        },
        "redis": {
            "alertas_activas_sobre_medicamento": alertas_activas,
            "alerta_escalada": alerta_generada,
        },
        "mongodb": {
            "historial_efectos_adversos_grupo_farmacologico": historial_ea,
        },
        "riesgo_alto": hay_grave or len(alertas_activas) > 0,
    }
    if errores:
        response["errores"] = errores
    return response
