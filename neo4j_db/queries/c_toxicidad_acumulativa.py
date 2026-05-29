"""
Consulta (c) — Toxicidad acumulativa en combinaciones de 3+ PA.

Detecta combinaciones de 3 o más medicamentos que, aunque individualmente
no están contraindicados de a pares, generan toxicidad acumulativa por
compartir la misma vía metabólica (enzimas CYP).

La condición NOT (pa1)-[:INTERACTUA_CON {severidad: 'grave'}]-(pa2) es
nativa de Cypher: el motor la evalúa como ausencia de arista, no como
una subconsulta. En SQL equivalente requeriría NOT EXISTS sobre un
self-join, extremadamente difícil de optimizar.

Uso:
    PYTHONPATH=. python3 -m neo4j_db.queries.c_toxicidad_acumulativa
"""

import sys
from neo4j_db.connection import get_driver

CYPHER = """
MATCH (pa1:PrincipioActivo), (pa2:PrincipioActivo), (pa3:PrincipioActivo)
WHERE pa1.via_metabolismo = pa2.via_metabolismo
  AND pa2.via_metabolismo = pa3.via_metabolismo
  AND elementId(pa1) < elementId(pa2) AND elementId(pa2) < elementId(pa3)
  AND NOT (pa1)-[:INTERACTUA_CON {severidad: 'grave'}]-(pa2)
  AND NOT (pa1)-[:INTERACTUA_CON {severidad: 'contraindicada'}]-(pa2)
  AND NOT (pa1)-[:INTERACTUA_CON {severidad: 'grave'}]-(pa3)
  AND NOT (pa1)-[:INTERACTUA_CON {severidad: 'contraindicada'}]-(pa3)
  AND NOT (pa2)-[:INTERACTUA_CON {severidad: 'grave'}]-(pa3)
  AND NOT (pa2)-[:INTERACTUA_CON {severidad: 'contraindicada'}]-(pa3)
MATCH (m1:Medicamento)-[:CONTIENE]->(pa1)
MATCH (m2:Medicamento)-[:CONTIENE]->(pa2)
MATCH (m3:Medicamento)-[:CONTIENE]->(pa3)
WHERE m1 <> m2 AND m2 <> m3 AND m1 <> m3
RETURN
  pa1.nombre                            AS pa1,
  pa2.nombre                            AS pa2,
  pa3.nombre                            AS pa3,
  pa1.via_metabolismo                   AS via_compartida,
  collect(DISTINCT m1.nombre_comercial) AS meds_con_pa1,
  collect(DISTINCT m2.nombre_comercial) AS meds_con_pa2,
  collect(DISTINCT m3.nombre_comercial) AS meds_con_pa3
LIMIT 20
"""

CYPHER_UPDATED = """
MATCH (pa1:PrincipioActivo), (pa2:PrincipioActivo), (pa3:PrincipioActivo)
WHERE pa1.via_metabolismo = pa2.via_metabolismo
  AND pa2.via_metabolismo = pa3.via_metabolismo
  AND pa1.nombre < pa2.nombre AND pa2.nombre < pa3.nombre
  AND NOT EXISTS {
        MATCH (pa1)-[i:INTERACTUA_CON]-(pa2)
        WHERE i.severidad IN ['grave', 'contraindicada']
  }
  AND NOT EXISTS {
        MATCH (pa1)-[i:INTERACTUA_CON]-(pa3)
        WHERE i.severidad IN ['grave', 'contraindicada']
  }
  AND NOT EXISTS {
        MATCH (pa2)-[i:INTERACTUA_CON]-(pa3)
        WHERE i.severidad IN ['grave', 'contraindicada']
  }
MATCH (m1:Medicamento)-[:CONTIENE]->(pa1)
MATCH (m2:Medicamento)-[:CONTIENE]->(pa2)
MATCH (m3:Medicamento)-[:CONTIENE]->(pa3)
WHERE m1 <> m2 AND m2 <> m3 AND m1 <> m3
RETURN
  pa1.nombre                            AS pa1,
  pa2.nombre                            AS pa2,
  pa3.nombre                            AS pa3,
  pa1.via_metabolismo                   AS via_compartida,
  collect(DISTINCT m1.nombre_comercial) AS meds_con_pa1,
  collect(DISTINCT m2.nombre_comercial) AS meds_con_pa2,
  collect(DISTINCT m3.nombre_comercial) AS meds_con_pa3
LIMIT 20
"""


def toxicidad_acumulativa() -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(CYPHER)
        rows = [r.data() for r in result]
    driver.close()
    return rows


def main():
    rows = toxicidad_acumulativa()

    print(f"\n=== Combinaciones con toxicidad acumulativa (vía metabólica compartida sin interacción directa grave): {len(rows)} ===\n")

    if not rows:
        print("  (sin combinaciones detectadas)")
        return

    for r in rows:
        print(f"  {r['pa1']} + {r['pa2']} + {r['pa3']}")
        print(f"    Vía compartida : {r['via_compartida']}")
        print(f"    Meds con PA1   : {', '.join(r['meds_con_pa1'][:3])}")
        print(f"    Meds con PA2   : {', '.join(r['meds_con_pa2'][:3])}")
        print(f"    Meds con PA3   : {', '.join(r['meds_con_pa3'][:3])}")
        print()


if __name__ == "__main__":
    main()
