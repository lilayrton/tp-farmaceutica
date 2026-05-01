"""
Consulta (b) — Red completa de un principio activo.

Dado un PA, devuelve:
  - Todos los medicamentos comerciales que lo contienen.
  - Todas sus interacciones con otros PA (en ambas direcciones).

Uso:
    PYTHONPATH=. python3 -m neo4j_db.queries.b_red_principio_activo Amoxicilina
"""

import sys
from neo4j_db.connection import get_driver

CYPHER = """
MATCH (pa:PrincipioActivo {nombre: $nombre})
OPTIONAL MATCH (m:Medicamento)-[:CONTIENE]->(pa)
OPTIONAL MATCH (pa)-[i:INTERACTUA_CON]-(otro:PrincipioActivo)
RETURN
  pa.nombre                                    AS principio_activo,
  pa.familia_quimica                           AS familia,
  pa.via_metabolismo                           AS via_metabolismo,
  collect(DISTINCT m.nombre_comercial)         AS en_medicamentos,
  collect(DISTINCT {
    con:       otro.nombre,
    tipo:      i.tipo,
    severidad: i.severidad,
    mecanismo: i.mecanismo
  })                                           AS interacciones
"""


def red_principio_activo(nombre: str) -> dict | None:
    driver = get_driver()
    with driver.session() as session:
        print(f"Parametros: {{'nombre': {nombre}}}")
        result = session.run(CYPHER, nombre=nombre)
        row = result.single()
        data = row.data() if row else None
    driver.close()
    return data


def main():
    if len(sys.argv) < 2:
        print("Uso: PYTHONPATH=. python3 -m neo4j_db.queries.b_red_principio_activo <nombre_pa>")
        sys.exit(1)

    nombre = " ".join(sys.argv[1:])
    data = red_principio_activo(nombre)

    if not data:
        print(f"No se encontró el principio activo '{nombre}'")
        sys.exit(1)

    print(f"\n=== Red de: {data['principio_activo']} ===")
    print(f"  Familia química : {data['familia']}")
    print(f"  Vía metabólica  : {data['via_metabolismo']}")

    meds = [m for m in data["en_medicamentos"] if m]
    print(f"\n  Medicamentos que lo contienen ({len(meds)}):")
    for m in sorted(meds):
        print(f"    - {m}")

    interacciones = [i for i in data["interacciones"] if i.get("con")]
    print(f"\n  Interacciones conocidas ({len(interacciones)}):")
    for i in sorted(interacciones, key=lambda x: x.get("severidad") or ""):
        print(
            f"    [{i.get('severidad','?'):15s}]  ↔ {i.get('con','')}  "
            f"({i.get('tipo','')})"
        )
        if i.get("mecanismo"):
            print(f"      {i['mecanismo']}")


if __name__ == "__main__":
    main()
