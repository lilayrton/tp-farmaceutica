"""
Consulta (d) — El PA más peligroso de la red.

Encuentra los principios activos con mayor cantidad de interacciones graves
o contraindicadas, ponderados por cuántos medicamentos los contienen
(mayor alcance = mayor riesgo sistémico).

Score de riesgo = total_interacciones_peligrosas × cantidad_medicamentos_que_lo_contienen

Por qué es mejor en grafo: count(i) sobre aristas de un nodo es O(grado),
no O(tabla completa). El índice idx_interaccion_severidad acelera el filtro.

Uso:
    PYTHONPATH=. python3 -m neo4j_db.queries.d_pa_mas_peligroso
    PYTHONPATH=. python3 -m neo4j_db.queries.d_pa_mas_peligroso --top 5
"""

import argparse
from neo4j_db.connection import get_driver

CYPHER = """
MATCH (pa:PrincipioActivo)-[i:INTERACTUA_CON]-(:PrincipioActivo)
WHERE i.severidad IN ['grave', 'contraindicada']
WITH pa,
     count(i)                                                        AS total_peligrosas,
     count(CASE WHEN i.severidad = 'contraindicada' THEN 1 END)     AS contraindicaciones,
     collect(DISTINCT i.tipo)                                        AS tipos
MATCH (m:Medicamento)-[:CONTIENE]->(pa)
RETURN
  pa.nombre                          AS principio_activo,
  pa.familia_quimica                 AS familia,
  total_peligrosas,
  contraindicaciones,
  count(DISTINCT m)                  AS presente_en_n_medicamentos,
  tipos                              AS tipos_interaccion,
  total_peligrosas * count(DISTINCT m) AS score_riesgo_sistemico
ORDER BY score_riesgo_sistemico DESC
LIMIT $top
"""


def pa_mas_peligroso(top: int = 10) -> list:
    driver = get_driver()
    with driver.session() as session:
        print(f"Parametros: {{'top': {top}}}")
        result = session.run(CYPHER, top=top)
        rows = [r.data() for r in result]
    driver.close()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=10, help="Cuántos PA mostrar (default: 10)")
    args = parser.parse_args()

    rows = pa_mas_peligroso(top=args.top)
    print(f"\n=== Top {args.top} principios activos más peligrosos de la red ===\n")
    print(f"  {'PA':30s}  {'familia':15s}  {'peligrosas':>10}  {'contrain.':>9}  {'en N meds':>9}  {'score':>8}")
    print(f"  {'-'*30}  {'-'*15}  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*8}")

    for r in rows:
        print(
            f"  {r['principio_activo']:30s}  "
            f"{r['familia']:15s}  "
            f"{r['total_peligrosas']:>10}  "
            f"{r['contraindicaciones']:>9}  "
            f"{r['presente_en_n_medicamentos']:>9}  "
            f"{r['score_riesgo_sistemico']:>8}"
        )

    if not rows:
        print("  (sin datos)")


if __name__ == "__main__":
    main()
