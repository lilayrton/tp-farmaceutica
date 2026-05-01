"""
Consulta (a) — Interacciones para una prescripción.

Dado un paciente con varios medicamentos prescriptos, detecta todas las
interacciones conocidas entre sus principios activos, ordenadas por
severidad descendente (contraindicada > grave > moderada > leve).

Por qué es mejor en grafo: en SQL requiere un JOIN O(n²) sobre todos los
pares de medicamentos del paciente. En Neo4j el motor recorre directamente
las aristas desde los nodos PA del paciente.

Uso:
    PYTHONPATH=. python3 -m neo4j_db.queries.a_interacciones_prescripcion PAC-2024-08821
"""

import sys
from neo4j_db.connection import get_driver

CYPHER = """
MATCH (pac:Paciente {id_anonimo: $id_anonimo})-[:TOMA]->(m:Medicamento)
      -[:CONTIENE]->(pa:PrincipioActivo)
WITH collect(DISTINCT pa) AS principios
UNWIND principios AS pa1
UNWIND principios AS pa2
WITH pa1, pa2 WHERE id(pa1) < id(pa2)
MATCH (pa1)-[i:INTERACTUA_CON]-(pa2)
RETURN
  pa1.nombre       AS principio_1,
  pa2.nombre       AS principio_2,
  i.tipo           AS tipo_interaccion,
  i.severidad      AS severidad,
  i.mecanismo      AS mecanismo
ORDER BY
  CASE i.severidad
    WHEN 'contraindicada' THEN 1
    WHEN 'grave'          THEN 2
    WHEN 'moderada'       THEN 3
    ELSE 4
  END
"""

SEVERIDAD_COLOR = {
    "contraindicada": "\033[91m",  # rojo
    "grave":          "\033[93m",  # amarillo
    "moderada":       "\033[94m",  # azul
}
RESET = "\033[0m"


def interacciones_prescripcion(id_anonimo: str) -> list:
    driver = get_driver()
    with driver.session() as session:
        print(f"Parametros: {{'id_anonimo': {id_anonimo}}}")
        result = session.run(CYPHER, id_anonimo=id_anonimo)
        rows = [r.data() for r in result]
    driver.close()
    return rows


def main():
    if len(sys.argv) < 2:
        print("Uso: PYTHONPATH=. python3 -m neo4j_db.queries.a_interacciones_prescripcion <id_anonimo>")
        sys.exit(1)

    id_anonimo = sys.argv[1]
    rows = interacciones_prescripcion(id_anonimo)

    print(f"\n=== Interacciones para paciente {id_anonimo}: {len(rows)} ===\n")

    if not rows:
        print("  (sin interacciones conocidas)")
        return

    for r in rows:
        sev = r["severidad"] or "leve"
        color = SEVERIDAD_COLOR.get(sev, "")
        print(
            f"  {color}{sev:15s}{RESET}  "
            f"{r['principio_1']} ↔ {r['principio_2']}"
        )
        print(f"    tipo: {r['tipo_interaccion']}  |  mecanismo: {r['mecanismo']}")
        print()


if __name__ == "__main__":
    main()
