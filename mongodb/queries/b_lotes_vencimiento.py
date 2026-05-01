"""
Consulta (b) — Lotes próximos a vencer con stock activo.

Identifica todos los lotes de medicamentos con stock activo que vencen
dentro de los próximos 90 días, ordenados por urgencia (días restantes).

El índice compuesto idx_lotes_vencimiento_stock permite al motor resolver
el range scan sin escanear documentos fuera del rango.

Uso:
    PYTHONPATH=. python3 -m mongodb.queries.b_lotes_vencimiento
    PYTHONPATH=. python3 -m mongodb.queries.b_lotes_vencimiento --dias 60
"""

import sys
from datetime import datetime, timedelta, timezone

from mongodb.connection import get_db


def lotes_proximos_vencer(dias: int = 90) -> list:
    db = get_db()
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(days=dias)

    print(f"Parametros: {{'ahora': {ahora}, 'limite': {limite}}}")

    pipeline = [
        {
            # Paso 1: Filtrado por fecha y stock.
            # Busca lotes que vencen entre HOY y los proximos N dias
            # y que aun tienen stock activo en distribuidores o en planta.
            "$match": {
                "fecha_vencimiento": {
                    "$gte": ahora,
                    "$lte": limite,
                },
                "estado_stock": {"$in": ["en_distribucion", "en_planta"]},
                "cantidad_producida": {"$gt": 0},
            }
        },
        {
            # Paso 2: Calculo dinamico de dias restantes.
            # Proyecta el tiempo faltante para facilitar la toma de decisiones.
            "$project": {
                "_id": 0,
                "numero_lote": 1,
                "medicamento_nombre": 1,
                "fecha_vencimiento": 1,
                "estado_stock": 1,
                "dias_para_vencer": {
                    "$dateDiff": {
                        "startDate": "$$NOW",
                        "endDate": "$fecha_vencimiento",
                        "unit": "day",
                    }
                },
            }
        },
        {"$sort": {"dias_para_vencer": 1}},
    ]

    return list(db.lotes.aggregate(pipeline))


def main():
    dias = 90
    if "--dias" in sys.argv:
        idx = sys.argv.index("--dias")
        try:
            dias = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    resultados = lotes_proximos_vencer(dias)

    print(f"\n=== Lotes próximos a vencer (próximos {dias} días): {len(resultados)} ===\n")

    if not resultados:
        print("  (sin lotes próximos a vencer con stock)")
        return

    print(f"  {'Lote':<20} {'Medicamento':<30} {'Días restantes':>15} {'Estado':<20}")
    print("  " + "-" * 87)
    for r in resultados:
        print(
            f"  {r['numero_lote']:<20} "
            f"{r['medicamento_nombre']:<30} "
            f"{r['dias_para_vencer']:>15} "
            f"{r['estado_stock']:<20}"
        )


if __name__ == "__main__":
    main()
