"""
Consulta (c) — Resumen de efectos adversos por gravedad y país.

Obtiene el resumen de efectos adversos reportados para un medicamento
en el último año, agrupados por nivel de gravedad y país de reporte.

Usa el índice idx_ea_med_gravedad_fecha. El pipeline agrupa por
{pais_reporte, gravedad}, ordena y proyecta campos renombrados.

Uso:
    PYTHONPATH=. python3 -m mongodb.queries.c_efectos_adversos <medicamento_id>
"""

import sys
from datetime import datetime, timedelta
from bson import ObjectId

from mongodb.connection import get_db


def resumen_efectos_adversos(medicamento_id: str) -> list:
    db = get_db()

    un_anio_atras = datetime.utcnow() - timedelta(days=365)

    print(f"Parametros: {{'medicamento_id': {medicamento_id}, 'un_anio_atras': {un_anio_atras}}}")

    pipeline = [
        {
            # Paso 0: Filtro por medicamento y ventana temporal (ultimo anio).
            # Usa el indice idx_ea_med_gravedad_fecha.
            "$match": {
                "medicamento_id": ObjectId(medicamento_id),
                "fecha": {"$gte": un_anio_atras},
            }
        },
        {
            # Paso 1: Agrupacion jerarquica.
            # Crea grupos unicos basados en la combinacion de Pais y Gravedad.
            "$group": {
                "_id": {"pais": "$pais_reporte", "gravedad": "$gravedad"},
                "total": {"$sum": 1},
            }
        },
        {
            # Paso 2: Ordenamiento logico.
            # Organiza los resultados alfabeticamente por pais
            # y luego por volumen de reportes (de mayor a menor).
            "$sort": {"_id.pais": 1, "total": -1}
        },
        {
            # Paso 3: Proyeccion y formateo.
            # Aplana la estructura de salida eliminando el objeto _id.
            "$project": {
                "_id": 0,
                "territorio": "$_id.pais",
                "nivel_gravedad": "$_id.gravedad",
                "total_casos_reportados": "$total",
            }
        },
    ]

    return list(db.efectos_adversos.aggregate(pipeline))


def main():
    if len(sys.argv) < 2:
        print("Uso: PYTHONPATH=. python3 -m mongodb.queries.c_efectos_adversos <medicamento_id>")
        sys.exit(1)

    med_id = sys.argv[1]

    try:
        resultados = resumen_efectos_adversos(med_id)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"\n=== Efectos adversos por país y gravedad (medicamento {med_id[:8]}…): {len(resultados)} grupos ===\n")

    if not resultados:
        print("  (sin reportes en el último año)")
        return

    print(f"  {'Territorio':<15} {'Gravedad':<15} {'Total casos':>12}")
    print("  " + "-" * 45)
    for r in resultados:
        print(
            f"  {r['territorio']:<15} "
            f"{r['nivel_gravedad']:<15} "
            f"{r['total_casos_reportados']:>12}"
        )


if __name__ == "__main__":
    main()
