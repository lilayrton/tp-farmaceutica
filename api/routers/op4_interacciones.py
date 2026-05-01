"""
OP-4 — Análisis de interacciones para un nuevo medicamento (2 motores)

MongoDB → recupera los principios activos del medicamento en desarrollo
Neo4j   → para cada PA, recorre el grafo y lista todas las interacciones conocidas

Redis no participa: esta es una consulta analítica/regulatoria sobre datos
históricos y relacionales. No hay datos operativos en tiempo real que
consultar — el medicamento aún no está en el mercado y no tiene alertas activas.
"""
from fastapi import APIRouter, Query
from bson import ObjectId

from mongodb.connection import get_db
from neo4j_db.queries.e_prediccion_interacciones import prediccion_interacciones

router = APIRouter()


def _mongo_principios_activos(medicamento_id: str) -> dict:
    db = get_db()
    try:
        med_oid = ObjectId(medicamento_id)
    except Exception:
        return {"error": f"ID de medicamento inválido: {medicamento_id}"}

    med = db.medicamentos.find_one({"_id": med_oid})
    if not med:
        return {"error": f"Medicamento '{medicamento_id}' no encontrado"}

    pa_ids = med.get("principios_activos", [])
    nombres_pa = []
    for pa_ref in pa_ids:
        pa_id = pa_ref.get("id") if isinstance(pa_ref, dict) else pa_ref
        if pa_id:
            pa_doc = db.principios_activos.find_one({"_id": ObjectId(str(pa_id))})
            if pa_doc:
                nombres_pa.append(pa_doc["nombre"])

    return {
        "medicamento_id": medicamento_id,
        "nombre_comercial": med.get("nombre_comercial"),
        "nombre_generico": med.get("nombre_generico"),
        "principios_activos": nombres_pa,
    }


@router.get(
    "/medicamento/{medicamento_id}/interacciones",
    summary="Análisis de interacciones para nuevo medicamento (2 motores)",
)
def analisis_interacciones(
    medicamento_id: str,
    principios_activos: list[str] = Query(
        default=[],
        description="Lista de nombres de principios activos (alternativa a buscar por ID)",
    ),
):
    """
    **OP-4** — Antes de aprobar un nuevo medicamento, mapea todas sus interacciones potenciales:

    - **MongoDB** recupera el medicamento y sus principios activos registrados.
    - **Neo4j** recorre el grafo de interacciones para cada principio activo y lista
      todas las combinaciones conocidas con medicamentos existentes, ordenadas por severidad.

    **¿Por qué Redis no participa?**
    Es un análisis regulatorio sobre un medicamento en desarrollo — no hay datos
    operativos en tiempo real que consultar. El medicamento no está en el mercado,
    por lo tanto no tiene alertas activas ni contadores en Redis.

    Podés pasar los nombres de principios activos directamente con el query param
    `principios_activos` en lugar de buscarlos por ID (útil para medicamentos en desarrollo
    que aún no están cargados en el catálogo).
    """
    errores = {}
    mongo_data = {}
    neo4j_data = {}
    nombres_pa = principios_activos  # puede venir directo del query param

    # 1. MongoDB — datos del medicamento y sus principios activos
    try:
        if medicamento_id and medicamento_id != "nuevo":
            mongo_data = _mongo_principios_activos(medicamento_id)
            if "error" not in mongo_data and not nombres_pa:
                nombres_pa = mongo_data.get("principios_activos", [])
        else:
            mongo_data = {"nota": "Medicamento en desarrollo — principios activos provistos directamente"}
    except Exception as e:
        errores["mongodb"] = str(e)

    # 2. Neo4j — predicción de interacciones
    try:
        if nombres_pa:
            interacciones = prediccion_interacciones(nombres_pa)
            neo4j_data = {
                "principios_activos_analizados": nombres_pa,
                "interacciones_detectadas": interacciones,
                "total": len(interacciones),
                "resumen_por_severidad": {
                    sev: sum(1 for i in interacciones if i.get("severidad") == sev)
                    for sev in ("contraindicada", "grave", "moderada", "leve")
                },
            }
        else:
            neo4j_data = {"error": "No se encontraron principios activos para analizar"}
    except Exception as e:
        errores["neo4j"] = str(e)

    response = {
        "operacion": "OP-4 Análisis de interacciones para nuevo medicamento",
        "motores": ["MongoDB", "Neo4j"],
        "medicamento_id": medicamento_id,
        "mongodb": mongo_data,
        "neo4j": neo4j_data,
    }
    if errores:
        response["errores"] = errores
    return response
