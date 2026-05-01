"""
Generador de datos de prueba para Redis.
Pobla las 5 estructuras de datos requeridas por el TP2.
"""
import json
import random
from datetime import datetime, timezone, timedelta

import redis

from redis_db.queries.a_alertas_farmacovigilancia import publicar_alerta, KEY as ALERTAS_KEY
from redis_db.queries.b_cadena_frio import registrar_lectura, STREAM_KEY
from redis_db.queries.c_control_acceso import (
    otorgar_acceso,
    encolar_reporte,
    COLA_KEY,
    _contador_key,
    VENTANA_CONTADOR_SEGUNDOS,
)

MEDICAMENTOS_SEED = [
    "MED001", "MED002", "MED003", "MED004", "MED005",
    "MED006", "MED007", "MED008",
]
ENSAYOS_SEED = ["ENS001", "ENS002", "ENS003"]
INVESTIGADORES_SEED = ["INV001", "INV002", "INV003", "INV004"]

# ── Alertas de farmacovigilancia ──────────────────────────────────────────────

ALERTAS_DEMO = [
    {"medicamento_id": "MED001", "severidad": 5, "tipo": "interaccion_grave",
     "descripcion": "Interacción crítica warfarina-aspirina detectada en 3 pacientes"},
    {"medicamento_id": "MED002", "severidad": 4, "tipo": "reaccion_adversa",
     "descripcion": "Reacción adversa hepática grave en pacientes mayores de 65 años"},
    {"medicamento_id": "MED003", "severidad": 5, "tipo": "lote_comprometido",
     "descripcion": "Lote LOT-2024-789 con posible contaminación microbiológica"},
    {"medicamento_id": "MED004", "severidad": 3, "tipo": "reaccion_adversa",
     "descripcion": "Reportes de erupciones cutáneas moderadas en Europa"},
    {"medicamento_id": "MED005", "severidad": 4, "tipo": "interaccion_grave",
     "descripcion": "Interacción con inhibidores de CYP3A4 aumenta toxicidad x3"},
    {"medicamento_id": "MED001", "severidad": 2, "tipo": "reaccion_adversa",
     "descripcion": "Náuseas leve-moderadas reportadas en ensayo fase III"},
    {"medicamento_id": "MED006", "severidad": 5, "tipo": "interaccion_grave",
     "descripcion": "Contraindicación absoluta con anticoagulantes orales confirmada"},
    {"medicamento_id": "MED007", "severidad": 3, "tipo": "lote_comprometido",
     "descripcion": "Ruptura de cadena de frío en distribución regional Norte"},
    {"medicamento_id": "MED002", "severidad": 1, "tipo": "reaccion_adversa",
     "descripcion": "Cefalea leve transitoria reportada (<2% de pacientes)"},
    {"medicamento_id": "MED008", "severidad": 4, "tipo": "reaccion_adversa",
     "descripcion": "Nefrotoxicidad acumulativa en tratamientos prolongados >6 meses"},
]


def seed_alertas(r: redis.Redis) -> int:
    r.delete(ALERTAS_KEY)
    for a in ALERTAS_DEMO:
        publicar_alerta(r, **a)
    print(f"  [Redis] {len(ALERTAS_DEMO)} alertas cargadas en SORTED SET '{ALERTAS_KEY}'")
    return len(ALERTAS_DEMO)


# ── Cadena de frío (STREAM) ───────────────────────────────────────────────────

def _generar_lecturas_vehiculo(vehiculo_id: str, n: int, incluir_ruptura: bool = False):
    """Genera n lecturas de temperatura para un vehículo."""
    lat_base = round(random.uniform(-35.0, -31.0), 4)
    lon_base = round(random.uniform(-64.0, -57.0), 4)
    lecturas = []
    for i in range(n):
        lat = round(lat_base + i * 0.01, 4)
        lon = round(lon_base + i * 0.01, 4)

        if incluir_ruptura and i >= n - 2:
            # Últimas 2 lecturas fuera de rango → ruptura
            temp = round(random.uniform(10.0, 18.0), 1)
        else:
            # Temperatura en rango normal 2-8°C
            temp = round(random.uniform(2.5, 7.5), 1)

        lecturas.append((vehiculo_id, temp, lat, lon))
    return lecturas


def seed_temperatura(r: redis.Redis) -> int:
    r.delete(STREAM_KEY)
    total = 0

    # VEH001: 10 lecturas normales
    for args in _generar_lecturas_vehiculo("VEH001", 10, incluir_ruptura=False):
        registrar_lectura(r, *args)
        total += 1

    # VEH002: 10 lecturas, últimas 2 fuera de rango → ruptura de cadena de frío
    for args in _generar_lecturas_vehiculo("VEH002", 10, incluir_ruptura=True):
        registrar_lectura(r, *args)
        total += 1

    # VEH003: 10 lecturas normales
    for args in _generar_lecturas_vehiculo("VEH003", 10, incluir_ruptura=False):
        registrar_lectura(r, *args)
        total += 1

    print(f"  [Redis] {total} lecturas de temperatura cargadas en STREAM '{STREAM_KEY}'")
    print("  [Redis] VEH002 tiene ruptura de cadena de frío (últimas 2 lecturas fuera de rango)")
    return total


# ── Cola de efectos adversos (LIST) ──────────────────────────────────────────

REPORTES_DEMO = [
    {"id": "REP001", "medicamento_id": "MED001", "paciente_id": "PAC042",
     "efecto": "hepatotoxicidad", "severidad": "grave", "pais": "Argentina"},
    {"id": "REP002", "medicamento_id": "MED003", "paciente_id": "PAC017",
     "efecto": "shock_anafilactico", "severidad": "grave", "pais": "Brasil"},
    {"id": "REP003", "medicamento_id": "MED005", "paciente_id": "PAC088",
     "efecto": "insuficiencia_renal", "severidad": "grave", "pais": "Chile"},
    {"id": "REP004", "medicamento_id": "MED002", "paciente_id": "PAC031",
     "efecto": "erupcion_cutanea", "severidad": "moderada", "pais": "Uruguay"},
    {"id": "REP005", "medicamento_id": "MED004", "paciente_id": "PAC055",
     "efecto": "nauseas_vomitos", "severidad": "leve", "pais": "Argentina"},
]


def seed_cola_reportes(r: redis.Redis) -> int:
    r.delete(COLA_KEY)
    for rep in REPORTES_DEMO:
        rep["timestamp"] = datetime.now(timezone.utc).isoformat()
        encolar_reporte(r, rep)
    print(f"  [Redis] {len(REPORTES_DEMO)} reportes cargados en LIST '{COLA_KEY}'")
    return len(REPORTES_DEMO)


# ── Control de acceso a ensayos (HASH + TTL) ─────────────────────────────────

ACCESOS_DEMO = [
    {"ensayo_id": "ENS001", "investigador_id": "INV001", "rol": "investigador",
     "institucion": "Hospital Italiano de Buenos Aires", "permisos": ["lectura", "escritura"]},
    {"ensayo_id": "ENS001", "investigador_id": "INV002", "rol": "auditor",
     "institucion": "ANMAT", "permisos": ["lectura"]},
    {"ensayo_id": "ENS002", "investigador_id": "INV003", "rol": "regulador",
     "institucion": "OPS/OMS", "permisos": ["lectura", "auditoria"]},
    {"ensayo_id": "ENS003", "investigador_id": "INV004", "rol": "investigador",
     "institucion": "UBA Farmacia", "permisos": ["lectura"]},
]


def seed_accesos(r: redis.Redis) -> int:
    for acc in ACCESOS_DEMO:
        otorgar_acceso(r, **acc)
    print(f"  [Redis] {len(ACCESOS_DEMO)} accesos a ensayos cargados (HASH+TTL)")
    return len(ACCESOS_DEMO)


# ── Contadores 24h de efectos adversos (STRING + EXPIRE) ─────────────────────

CONTADORES_DEMO = [
    {"medicamento_id": "MED001", "conteo": 8},   # supera umbral (>5)
    {"medicamento_id": "MED002", "conteo": 3},   # bajo umbral
    {"medicamento_id": "MED003", "conteo": 6},   # supera umbral
    {"medicamento_id": "MED004", "conteo": 1},   # bajo umbral
]


def seed_contadores(r: redis.Redis) -> int:
    for item in CONTADORES_DEMO:
        key = _contador_key(item["medicamento_id"])
        r.set(key, item["conteo"])
        r.expire(key, VENTANA_CONTADOR_SEGUNDOS)
    print(f"  [Redis] {len(CONTADORES_DEMO)} contadores de 24h cargados (STRING+EXPIRE)")
    print("  [Redis] MED001 y MED003 superan el umbral de 5 reportes en 24h")
    return len(CONTADORES_DEMO)


# ── Orquestador principal ─────────────────────────────────────────────────────

def seed_redis(r: redis.Redis) -> dict:
    """Pobla todas las estructuras Redis con datos de prueba."""
    print("\n[Redis] Iniciando carga de datos de prueba...")
    resultado = {
        "alertas": seed_alertas(r),
        "lecturas_temperatura": seed_temperatura(r),
        "reportes_cola": seed_cola_reportes(r),
        "accesos_ensayos": seed_accesos(r),
        "contadores": seed_contadores(r),
    }
    print("[Redis] Carga completada.\n")
    return resultado


if __name__ == "__main__":
    from redis_db.connection import get_redis

    r = get_redis()
    resumen = seed_redis(r)
    print(f"Resumen: {json.dumps(resumen, indent=2)}")
