"""
Consulta (e) — Señal de farmacovigilancia.

Detecta medicamentos con más de 3 reportes de efectos adversos graves
en el último semestre. Clasifica la alerta en BAJA / MODERADA / CRITICA.

Usa $dateAdd/$expr para evaluar la ventana temporal dentro del motor.
$switch clasifica automáticamente la urgencia.

Uso:
    PYTHONPATH=. python3 -m mongodb.queries.e_senal_farmacovigilancia
    PYTHONPATH=. python3 -m mongodb.queries.e_senal_farmacovigilancia --umbral 5
"""

import sys

from mongodb.connection import get_db

NIVEL_COLOR = {
    "BAJA":     "\033[94m",
    "MODERADA": "\033[93m",
    "CRITICA":  "\033[91m",
}
RESET = "\033[0m"


def senal_farmacovigilancia(umbral: int = 3) -> list:
    db = get_db()

    print(f"Parametros: {{'umbral': {umbral}}}")

    pipeline = [
        {
            # 1. Filtro dinamico: Ultimos 6 meses y gravedad "grave"
            "$match": {
                "gravedad": "grave",
                "$expr": {
                    "$gte": [
                        "$fecha",
                        {"$dateAdd": {"startDate": "$$NOW", "unit": "month", "amount": -6}},
                    ]
                },
            }
        },
        {
            # 2. Sumarizacion por entidad de medicamento
            "$group": {
                "_id": "$medicamento_id",
                "total": {"$sum": 1},
            }
        },
        {
            # 3. Umbral de senal de seguridad
            "$match": {"total": {"$gt": umbral}}
        },
        {
            # 4. Enriquecimiento de datos (join con medicamentos)
            "$lookup": {
                "from": "medicamentos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "med_info",
            }
        },
        {
            # 5. Categorizacion de riesgo y formato de salida
            "$project": {
                "_id": 0,
                "medicamento": {"$arrayElemAt": ["$med_info.nombre_comercial", 0]},
                "reportes_detectados": "$total",
                "nivel_alerta": {
                    "$switch": {
                        "branches": [
                            {"case": {"$lte": ["$total", 5]}, "then": "BAJA"},
                            {"case": {"$lte": ["$total", 10]}, "then": "MODERADA"},
                        ],
                        "default": "CRITICA",
                    }
                },
            }
        },
        {"$sort": {"reportes_detectados": -1}},
    ]

    return list(db.efectos_adversos.aggregate(pipeline))


def main():
    umbral = 3
    if "--umbral" in sys.argv:
        idx = sys.argv.index("--umbral")
        try:
            umbral = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    resultados = senal_farmacovigilancia(umbral)

    print(f"\n=== Señal de farmacovigilancia (umbral >{umbral} reportes graves en 6 meses): {len(resultados)} ===\n")

    if not resultados:
        print("  (sin señales detectadas)")
        return

    print(f"  {'Medicamento':<35} {'Reportes':>9}  {'Nivel alerta'}")
    print("  " + "-" * 60)
    for r in resultados:
        nivel = r["nivel_alerta"]
        color = NIVEL_COLOR.get(nivel, "")
        print(
            f"  {r['medicamento']:<35} "
            f"{r['reportes_detectados']:>9}  "
            f"{color}{nivel}{RESET}"
        )


if __name__ == "__main__":
    main()
