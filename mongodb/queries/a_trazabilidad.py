"""
Consulta (a) — Trazabilidad completa de un lote.

Dado un número de lote, reconstruye el camino completo desde la planta
de fabricación hasta el último punto de dispensación.

La cadena de distribución está embebida en el documento del lote,
por lo que la consulta es O(1): un solo $match + $project sin JOINs.

Uso:
    PYTHONPATH=. python3 -m mongodb.queries.a_trazabilidad LOT-2024-00451
"""

import json
import sys
from bson import json_util

from mongodb.connection import get_db


PIPELINE_TRAZABILIDAD = lambda numero_lote: [
    {
        # Paso 1: Filtrado por el identificador de negocio.
        # Utiliza el indice unico definido sobre "numero_lote".
        "$match": {"numero_lote": numero_lote}
    },
    {
        # Paso 2: Transformacion y limpieza de salida.
        # Selecciona solo los campos relevantes para el reporte de trazabilidad.
        "$project": {
            "_id": 0,
            "lote": "$numero_lote",
            "producto_id": "$medicamento_id",
            "planta_origen": "$planta_produccion",
            "fecha_fabricacion": 1,
            "fecha_vencimiento": 1,
            "historial_trazabilidad": "$cadena_distribucion",
        }
    },
]


def trazabilidad_lote(numero_lote: str) -> dict | None:
    db = get_db()

    print(f"Parametros: {{'numero_lote': {numero_lote}}}")
    
    resultados = list(db.lotes.aggregate(PIPELINE_TRAZABILIDAD(numero_lote)))
    return resultados[0] if resultados else None


def main():
    if len(sys.argv) < 2:
        print("Uso: PYTHONPATH=. python3 -m mongodb.queries.a_trazabilidad <numero_lote>")
        sys.exit(1)

    numero_lote = sys.argv[1]
    resultado = trazabilidad_lote(numero_lote)

    if resultado is None:
        print(f"No se encontró el lote '{numero_lote}'")
        sys.exit(1)

    print(f"\n=== Trazabilidad del lote: {numero_lote} ===\n")
    print(json.dumps(json_util.loads(json_util.dumps(resultado)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
