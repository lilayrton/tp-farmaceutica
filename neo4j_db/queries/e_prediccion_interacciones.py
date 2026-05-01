"""
Consulta (e) — Predicción de interacciones para un nuevo medicamento.

Dado un medicamento en desarrollo con sus principios activos conocidos,
predice todas las interacciones potenciales con medicamentos ya existentes
en el mercado, ordenadas por severidad descendente.

Por qué es mejor en grafo: la traversía (PA)-[:INTERACTUA_CON*1..3]-(otro)
descubre rutas indirectas sin cambiar la query. En SQL requiere conocer el
schema de antemano y no puede descubrir caminos de longitud variable.

Uso:
    PYTHONPATH=. python3 -m neo4j_db.queries.e_prediccion_interacciones Amoxicilina Clavulanato
    PYTHONPATH=. python3 -m neo4j_db.queries.e_prediccion_interacciones "Atorvastatina"
"""

import sys
from neo4j_db.connection import get_driver

CYPHER = """
WITH $pa_del_nuevo AS pa_del_nuevo
MATCH (pa_nuevo:PrincipioActivo)
WHERE pa_nuevo.nombre IN pa_del_nuevo
MATCH (pa_nuevo)-[i:INTERACTUA_CON]-(pa_existente:PrincipioActivo)
WHERE NOT pa_existente.nombre IN pa_del_nuevo
MATCH (med_existente:Medicamento)-[:CONTIENE]->(pa_existente)
WHERE med_existente.estado = 'activo'
RETURN
  pa_nuevo.nombre                               AS pa_propio,
  pa_existente.nombre                           AS pa_en_conflicto,
  i.tipo                                        AS tipo_interaccion,
  i.severidad                                   AS severidad,
  i.mecanismo                                   AS mecanismo,
  collect(DISTINCT med_existente.nombre_comercial) AS medicamentos_afectados
ORDER BY
  CASE i.severidad
    WHEN 'contraindicada' THEN 1
    WHEN 'grave'          THEN 2
    WHEN 'moderada'       THEN 3
    ELSE 4
  END, pa_existente.nombre
"""

SEVERIDAD_COLOR = {
    "contraindicada": "\033[91m",
    "grave":          "\033[93m",
    "moderada":       "\033[94m",
}
RESET = "\033[0m"


def prediccion_interacciones(pa_del_nuevo: list[str]) -> list:
    driver = get_driver()
    with driver.session() as session:
        print(f"Parametros: {{'pa_del_nuevo': {pa_del_nuevo}}}")
        result = session.run(CYPHER, pa_del_nuevo=pa_del_nuevo)
        rows = [r.data() for r in result]
    driver.close()
    return rows


def main():
    if len(sys.argv) < 2:
        print("Uso: PYTHONPATH=. python3 -m neo4j_db.queries.e_prediccion_interacciones <PA1> [PA2] ...")
        sys.exit(1)

    pa_del_nuevo = sys.argv[1:]
    rows = prediccion_interacciones(pa_del_nuevo)

    print(f"\n=== Predicción de interacciones para nuevo med con PA: {', '.join(pa_del_nuevo)} ===")
    print(f"    {len(rows)} conflictos detectados con medicamentos existentes\n")

    if not rows:
        print("  (sin interacciones detectadas — seguro para prescribir junto a los meds actuales)")
        return

    for r in rows:
        sev = r["severidad"] or "leve"
        color = SEVERIDAD_COLOR.get(sev, "")
        meds = ", ".join(r["medicamentos_afectados"][:5])
        if len(r["medicamentos_afectados"]) > 5:
            meds += f" (+{len(r['medicamentos_afectados']) - 5} más)"
        print(
            f"  {color}{sev:15s}{RESET}  "
            f"{r['pa_propio']} ↔ {r['pa_en_conflicto']}  ({r['tipo_interaccion']})"
        )
        print(f"    Mecanismo        : {r['mecanismo']}")
        print(f"    Meds afectados   : {meds}")
        print()


if __name__ == "__main__":
    main()
