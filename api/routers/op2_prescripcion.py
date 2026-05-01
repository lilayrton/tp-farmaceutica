"""
OP-2 — Verificación de prescripción y detección de riesgos (3 motores)

Orden de consultas:
  1. Neo4j  → interacciones del paciente con el nuevo medicamento
  2. Redis  → alertas activas sobre el medicamento a prescribir
  3. MongoDB→ historial de efectos adversos del paciente con medicamentos similares
  4. Redis  → si hay interacción grave, escalar/publicar alerta de alta severidad
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


def _neo4j_interacciones_paciente(paciente_id: str) -> list:
    driver = get_driver()
    cypher = """
    MATCH (pac:Paciente {id_anonimo: $paciente_id})-[:TOMA]->(m:Medicamento)
          -[:CONTIENE]->(pa:PrincipioActivo)
    WITH collect(DISTINCT pa) AS principios
    UNWIND principios AS pa1
    UNWIND principios AS pa2
    WITH pa1, pa2 WHERE id(pa1) < id(pa2)
    MATCH (pa1)-[i:INTERACTUA_CON]-(pa2)
    RETURN pa1.nombre AS principio_1, pa2.nombre AS principio_2,
           i.tipo AS tipo_interaccion, i.severidad AS severidad, i.mecanismo AS mecanismo
    ORDER BY
      CASE i.severidad
        WHEN 'contraindicada' THEN 1
        WHEN 'grave'          THEN 2
        WHEN 'moderada'       THEN 3
        ELSE 4
      END
    """
    with driver.session() as session:
        result = session.run(cypher, paciente_id=paciente_id)
        return [r.data() for r in result]


def _mongo_historial_efectos(medicamento_id: str) -> list:
    db = get_db()
    try:
        med_oid = ObjectId(medicamento_id)
    except Exception:
        return []
    seis_meses = datetime.utcnow() - timedelta(days=180)
    pipeline = [
        {"$match": {"medicamento_id": med_oid, "fecha": {"$gte": seis_meses}}},
        {"$sort": {"fecha": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "efecto": "$termino_meddra",
                "gravedad": 1,
                "pais": "$pais_reporte",
                "fecha": 1,
            }
        },
    ]
    return list(db.efectos_adversos.aggregate(pipeline))


@router.post("/prescripcion/verificar", summary="Verificar prescripción y detectar riesgos (3 motores)")
def verificar_prescripcion(req: VerificarPrescripcionRequest):
    """
    **OP-2** — Antes de prescribir un medicamento, verifica riesgos en tiempo real:

    1. **Neo4j** detecta interacciones existentes en el grafo del paciente.
    2. **Redis** consulta alertas activas sobre el medicamento.
    3. **MongoDB** recupera el historial de efectos adversos recientes.
    4. **Redis** publica alerta de alta severidad si hay interacción grave o contraindicada.
    """
    errores = {}
    interacciones = []
    alertas_activas = []
    historial_ea = []
    alerta_generada = None

    # 1. Neo4j — interacciones del paciente
    try:
        interacciones = _neo4j_interacciones_paciente(req.paciente_id)
    except Exception as e:
        errores["neo4j"] = str(e)

    # 2. Redis — alertas activas sobre el medicamento
    try:
        r = get_redis()
        todas = listar_alertas_activas(r)
        alertas_activas = [a for a in todas if a.get("medicamento_id") == req.medicamento_id]
    except Exception as e:
        errores["redis_lectura"] = str(e)

    # 3. MongoDB — historial de efectos adversos
    try:
        historial_ea = _mongo_historial_efectos(req.medicamento_id)
    except Exception as e:
        errores["mongodb"] = str(e)

    # 4. Redis — escalar/publicar alerta si hay interacción grave
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
        "neo4j": {
            "interacciones_detectadas": interacciones,
            "total": len(interacciones),
        },
        "redis": {
            "alertas_activas_sobre_medicamento": alertas_activas,
            "alerta_escalada": alerta_generada,
        },
        "mongodb": {
            "historial_efectos_adversos_recientes": historial_ea,
        },
        "riesgo_alto": hay_grave or len(alertas_activas) > 0,
    }
    if errores:
        response["errores"] = errores
    return response
