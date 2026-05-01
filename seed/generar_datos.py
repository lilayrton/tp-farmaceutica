#!/usr/bin/env python3
"""
generar_datos.py — Generador de datos de prueba coherentes para MongoDB, Neo4j y Redis.

Uso:
    python generar_datos.py                    # genera archivos JSON + .cypher
    python generar_datos.py --mongo-load       # además carga en MongoDB local
    python generar_datos.py --neo4j-load       # además carga en Neo4j local
    python generar_datos.py --redis-load       # además carga en Redis local
    python generar_datos.py --all              # genera + carga en los tres motores

Salida (carpeta ./output/):
    mongodb/
        principios_activos.json
        medicamentos.json
        distribuidores.json
        lotes.json
        ensayos_clinicos.json
        efectos_adversos.json
    neo4j/
        carga_neo4j.cypher      <- ejecutar en cypher-shell
        resumen_nodos.txt

Requiere: pip install faker pymongo neo4j redis
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from bson import ObjectId

# ── Ajustar path para imports locales ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config import *
from datos_maestros import PRINCIPIOS_ACTIVOS_MAESTROS
from generador_mongo import (
    generar_principios_activos,
    generar_medicamentos,
    generar_distribuidores,
    generar_lotes,
    generar_ensayos,
    generar_efectos_adversos,
)
from generador_neo4j import GeneradorNeo4j

OUTPUT_DIR = Path(__file__).parent / "output"


# ── Serialización JSON compatible con ObjectId y datetime ────────────────────
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        from bson import ObjectId
        from datetime import datetime
        if isinstance(obj, ObjectId):
            return {"$oid": str(obj)}
        if isinstance(obj, datetime):
            return {"$date": obj.isoformat()}
        return super().default(obj)


def guardar_json(docs: list, path: Path):
    """Guarda documentos como JSON, uno por línea (formato mongoimport)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, cls=MongoJSONEncoder, ensure_ascii=False) + "\n")
    print(f"  [OK] {path.name}: {len(docs)} documentos")


# ── Carga en MongoDB ──────────────────────────────────────────────────────────
def cargar_mongodb(colecciones: dict):
    """Carga los documentos en MongoDB usando pymongo."""
    try:
        from pymongo import MongoClient
    except ImportError:
        print("  [ERROR] pymongo no instalado. Ejecutar: pip install pymongo")
        return

    print(f"\n→ Conectando a MongoDB en {MONGO_URI}...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.server_info()
    except Exception as e:
        print(f"  [ERROR] No se pudo conectar a MongoDB: {e}")
        return

    db = client[MONGO_DB]

    for nombre_col, docs in colecciones.items():
        col = db[nombre_col]
        col.drop()
        if docs:
            col.insert_many(docs)
        print(f"  [OK] {nombre_col}: {len(docs)} documentos insertados")

    # Crear índices
    print("\n→ Creando índices MongoDB...")
    db.lotes.create_index([("numero_lote", 1)], unique=True, name="idx_lotes_numero")
    db.lotes.create_index(
        [("fecha_vencimiento", 1), ("estado_stock", 1)],
        name="idx_lotes_vencimiento_stock"
    )
    db.efectos_adversos.create_index(
        [("medicamento_id", 1), ("gravedad", 1), ("fecha", -1)],
        name="idx_ea_med_gravedad_fecha"
    )
    db.ensayos_clinicos.create_index(
        [("fase", 1), ("estado", 1)],
        name="idx_ensayos_fase_estado"
    )
    print("  [OK] 4 índices creados")
    client.close()


# ── Carga en Neo4j ────────────────────────────────────────────────────────────
def cargar_neo4j(cypher_path: Path):
    """Ejecuta el script Cypher en Neo4j usando el driver bolt."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("  [ERROR] neo4j no instalado. Ejecutar: pip install neo4j")
        return

    print(f"\n→ Conectando a Neo4j en {NEO4J_URI}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        driver.verify_connectivity()
    except Exception as e:
        print(f"  [ERROR] No se pudo conectar a Neo4j: {e}")
        return

    cypher_text = cypher_path.read_text(encoding="utf-8")

    # Separar por sentencias (punto y coma al final de línea)
    sentencias = []
    buffer = []
    for line in cypher_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped == "":
            continue
        buffer.append(stripped)
        if stripped.endswith(";"):
            sentencias.append(" ".join(buffer).rstrip(";"))
            buffer = []

    print(f"  → Ejecutando {len(sentencias)} sentencias Cypher...")
    errores = 0
    with driver.session() as session:
        for i, stmt in enumerate(sentencias):
            try:
                session.run(stmt)
            except Exception as e:
                errores += 1
                if errores <= 5:  # mostrar solo primeros errores
                    print(f"  [WARN] Sentencia {i+1}: {e}")

    print(f"  [OK] {len(sentencias) - errores} sentencias ejecutadas. {errores} errores.")
    driver.close()


# ── Resumen de estadísticas ───────────────────────────────────────────────────
def imprimir_resumen(colecciones_mongo: dict, stats_neo4j: dict):
    print("\n" + "="*60)
    print("RESUMEN DE GENERACIÓN")
    print("="*60)
    print("\nMongoDB:")
    for nombre, docs in colecciones_mongo.items():
        print(f"  {nombre:<25} {len(docs):>5} documentos")

    print("\nNeo4j:")
    for nombre, cantidad in stats_neo4j.items():
        print(f"  {nombre:<25} {cantidad:>5}")
    print("="*60)

    # Verificaciones de garantías
    print("\nGarantías del enunciado:")
    from datetime import datetime, timedelta
    from collections import Counter

    lotes = colecciones_mongo.get("lotes", [])
    hoy = datetime.now()
    proximos = sum(1 for l in lotes
                   if l.get("fecha_vencimiento") and (l["fecha_vencimiento"] - hoy).days < 90
                   and l.get("estado_stock") in ["en_distribucion", "en_planta"])
    print(f"  Lotes próximos a vencer (<90d): {proximos} (mínimo 20)")

    ensayos = colecciones_mongo.get("ensayos_clinicos", [])
    fase3_activos = sum(1 for e in ensayos if e.get("fase") == "III" and e.get("estado") == "activo")
    print(f"  Ensayos fase III activos:        {fase3_activos} (mínimo 5)")

    ea = colecciones_mongo.get("efectos_adversos", [])
    hace6m = hoy - timedelta(days=180)
    graves_recientes = [e for e in ea if e.get("gravedad") == "grave"
                        and e.get("fecha") is not None
                        and e["fecha"] >= hace6m]
    conteo_meds = Counter(e.get("medicamento_nombre") for e in graves_recientes)
    meds_señal = sum(1 for c in conteo_meds.values() if c > 3)
    print(f"  Medicamentos con señal (>3 EA graves semestre): {meds_señal} (mínimo {MEDS_CON_SEÑAL_FARMACOVIG})")
    print()


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generador de datos de prueba — TP Farmacéutica")
    parser.add_argument("--mongo-load", action="store_true", help="Cargar datos en MongoDB")
    parser.add_argument("--neo4j-load", action="store_true", help="Cargar datos en Neo4j")
    parser.add_argument("--redis-load", action="store_true", help="Cargar datos en Redis")
    parser.add_argument("--all",        action="store_true", help="Generar y cargar en los tres motores")
    args = parser.parse_args()

    if args.all:
        args.mongo_load = True
        args.neo4j_load = True
        args.redis_load = True

    print("="*60)
    print("GENERADOR DE DATOS — TP FARMACÉUTICA (Tema 13)")
    print("="*60)
    t0 = time.time()

    # ── 1. Generar datos MongoDB ─────────────────────────────────────────────
    print("\n[1/5] Generando principios activos...")
    pa_docs, pa_id_map = generar_principios_activos(PRINCIPIOS_ACTIVOS_MAESTROS)

    print("[2/5] Generando medicamentos...")
    med_docs, med_id_map = generar_medicamentos(pa_docs, pa_id_map)

    print("[3/5] Generando distribuidores, lotes, ensayos y efectos adversos...")
    dist_docs, _ = generar_distribuidores()
    lote_docs     = generar_lotes(med_docs, dist_docs)
    ensayo_docs   = generar_ensayos(med_docs, pa_id_map)
    ea_docs       = generar_efectos_adversos(med_docs, lote_docs, pa_docs)

    colecciones_mongo = {
        "principios_activos": pa_docs,
        "medicamentos":       med_docs,
        "distribuidores":     dist_docs,
        "lotes":              lote_docs,
        "ensayos_clinicos":   ensayo_docs,
        "efectos_adversos":   ea_docs,
    }

    # ── 2. Generar datos Neo4j ───────────────────────────────────────────────
    print("[4/5] Generando grafo Neo4j...")
    gen = GeneradorNeo4j(pa_docs, pa_id_map, med_docs, ensayo_docs)

    nodos_pa      = gen.gen_nodos_pa()
    nodos_med     = gen.gen_nodos_medicamento()
    nodos_pat     = gen.gen_nodos_patologia()
    nodos_ensayo  = gen.gen_nodos_ensayo()
    nodos_pac     = gen.gen_nodos_paciente()

    rels_contiene   = gen.gen_relaciones_contiene()
    rels_interactua = gen.gen_relaciones_interactua()
    rels_afecta     = gen.gen_relaciones_afecta()
    rels_estudia    = gen.gen_relaciones_estudia()
    rels_toma       = gen.gen_relaciones_toma(nodos_pac, rels_interactua)
    rels_modifica   = gen.gen_relaciones_modifica_interaccion(rels_interactua)

    stats_neo4j = {
        ":PrincipioActivo":        len(nodos_pa),
        ":Medicamento":            len(nodos_med),
        ":Patologia":              len(nodos_pat),
        ":EnsayoClinico":          len(nodos_ensayo),
        ":Paciente":               len(nodos_pac),
        "[:CONTIENE]":             len(rels_contiene),
        "[:INTERACTUA_CON]":       len(rels_interactua),
        "[:AFECTA]":               len(rels_afecta),
        "[:ESTUDIA]":              len(rels_estudia),
        "[:TOMA]":                 len(rels_toma),
        "[:MODIFICA_INTERACCION]": len(rels_modifica),
    }

    # ── 3. Guardar archivos ──────────────────────────────────────────────────
    print("[5/5] Guardando archivos...")
    mongo_dir = OUTPUT_DIR / "mongodb"
    neo4j_dir = OUTPUT_DIR / "neo4j"

    print("\n  MongoDB (JSON para mongoimport):")
    for nombre, docs in colecciones_mongo.items():
        guardar_json(docs, mongo_dir / f"{nombre}.json")

    print("\n  Neo4j (script Cypher):")
    cypher_path = neo4j_dir / "carga_neo4j.cypher"
    neo4j_dir.mkdir(parents=True, exist_ok=True)
    gen.exportar_cypher(
        str(cypher_path),
        nodos_pa, nodos_med, nodos_pat, nodos_ensayo, nodos_pac,
        rels_contiene, rels_interactua, rels_afecta, rels_estudia, rels_toma,
        rels_modifica
    )
    print(f"  [OK] carga_neo4j.cypher: {sum(stats_neo4j.values())} elementos")

    # ── 4. Carga en motores (opcional) ──────────────────────────────────────
    if args.mongo_load:
        print("\n→ Cargando en MongoDB...")
        cargar_mongodb(colecciones_mongo)

    if args.neo4j_load:
        print("\n→ Cargando en Neo4j...")
        cargar_neo4j(cypher_path)

    if args.redis_load:
        print("\n→ Cargando en Redis...")
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).parent.parent))
            from redis_db.connection import get_redis
            from seed.generador_redis import seed_redis
            r = get_redis()
            r.ping()
            seed_redis(r)
        except Exception as e:
            print(f"  [ERROR] No se pudo conectar a Redis: {e}")

    # ── 5. Resumen ───────────────────────────────────────────────────────────
    imprimir_resumen(colecciones_mongo, stats_neo4j)

    elapsed = time.time() - t0
    print(f"Tiempo total: {elapsed:.1f}s")
    print(f"\nArchivos en: {OUTPUT_DIR.resolve()}")
    print("\nPara importar manualmente:")
    print(f"  mongoimport --db {MONGO_DB} --collection medicamentos --file output/mongodb/medicamentos.json")
    print(f"  cypher-shell -u {NEO4J_USER} -p <pass> --file output/neo4j/carga_neo4j.cypher")


if __name__ == "__main__":
    main()
