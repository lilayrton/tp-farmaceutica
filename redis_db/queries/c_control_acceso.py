"""
HASH  acceso:ensayo:{ensayo_id}:{investigador_id}  — control de acceso con TTL
LIST  cola:efectos_adversos                        — cola FIFO de reportes pendientes
STRING contador:efectos:{medicamento_id}           — contador 24h con EXPIRE automático
"""
import json
from datetime import datetime, timezone

import redis

from redis_db.queries.a_alertas_farmacovigilancia import publicar_alerta

COLA_KEY = "cola:efectos_adversos"
TTL_POR_ROL = {
    "investigador": 28800,  # 8 h
    "auditor": 14400,       # 4 h
    "regulador": 86400,     # 24 h
}
UMBRAL_ALERTAS = 5
VENTANA_CONTADOR_SEGUNDOS = 86400  # 24 h


def _acceso_key(ensayo_id: str, investigador_id: str) -> str:
    return f"acceso:ensayo:{ensayo_id}:{investigador_id}"


def _contador_key(medicamento_id: str) -> str:
    return f"contador:efectos:{medicamento_id}"


# ── Acceso a ensayos clínicos ────────────────────────────────────────────────

def otorgar_acceso(
    r: redis.Redis,
    ensayo_id: str,
    investigador_id: str,
    rol: str,
    institucion: str = "",
    permisos: list[str] | None = None,
) -> dict:
    """Otorga acceso temporal a un ensayo clínico según el rol del investigador."""
    if rol not in TTL_POR_ROL:
        raise ValueError(f"Rol inválido: {rol}. Válidos: {list(TTL_POR_ROL)}")

    ttl = TTL_POR_ROL[rol]
    key = _acceso_key(ensayo_id, investigador_id)
    permisos_str = ",".join(permisos or ["lectura"])

    r.hset(key, mapping={
        "investigador_id": investigador_id,
        "ensayo_id": ensayo_id,
        "rol": rol,
        "institucion": institucion,
        "permisos": permisos_str,
        "otorgado_en": datetime.now(timezone.utc).isoformat(),
    })
    r.expire(key, ttl)

    return {
        "key": key,
        "ttl_segundos": ttl,
        "permisos": permisos_str,
        "expira_en_horas": ttl / 3600,
    }


def verificar_acceso(
    r: redis.Redis,
    ensayo_id: str,
    investigador_id: str,
) -> dict:
    """Verifica si un investigador tiene acceso vigente a un ensayo."""
    key = _acceso_key(ensayo_id, investigador_id)
    if not r.exists(key):
        return {"acceso_vigente": False, "motivo": "Sin acceso o acceso expirado"}

    datos = r.hgetall(key)
    ttl_restante = r.ttl(key)
    datos["ttl_restante_segundos"] = ttl_restante
    datos["acceso_vigente"] = True
    return datos


# ── Cola de efectos adversos ─────────────────────────────────────────────────

def encolar_reporte(r: redis.Redis, reporte: dict) -> int:
    """Encola un reporte de efecto adverso para evaluación médica (LPUSH).
    Retorna el tamaño actual de la cola."""
    if "timestamp" not in reporte:
        reporte["timestamp"] = datetime.now(timezone.utc).isoformat()
    return r.lpush(COLA_KEY, json.dumps(reporte))


def tomar_reporte(r: redis.Redis) -> dict | None:
    """El médico evaluador toma el próximo reporte pendiente (RPOP — FIFO)."""
    raw = r.rpop(COLA_KEY)
    return json.loads(raw) if raw else None


def tamanio_cola(r: redis.Redis) -> int:
    """Retorna el número de reportes pendientes en la cola."""
    return r.llen(COLA_KEY)


# ── Contador 24h de efectos adversos por medicamento ─────────────────────────

def incrementar_contador_y_alertar(
    r: redis.Redis,
    medicamento_id: str,
    umbral: int = UMBRAL_ALERTAS,
    descripcion_reporte: str = "",
) -> dict:
    """Incrementa el contador de reportes del medicamento en las últimas 24h.
    Si se supera el umbral, publica una alerta en el SORTED SET."""
    key = _contador_key(medicamento_id)
    es_nueva_clave = not r.exists(key)
    conteo = r.incr(key)

    if es_nueva_clave:
        r.expire(key, VENTANA_CONTADOR_SEGUNDOS)

    alerta_disparada = None
    if conteo >= umbral:
        alerta = publicar_alerta(
            r,
            medicamento_id=medicamento_id,
            severidad=4,
            tipo="reaccion_adversa",
            descripcion=(
                descripcion_reporte
                or f"Medicamento {medicamento_id} superó umbral: {conteo} reportes en 24h"
            ),
        )
        alerta_disparada = alerta

    return {
        "medicamento_id": medicamento_id,
        "conteo_24h": conteo,
        "umbral": umbral,
        "alerta_disparada": alerta_disparada is not None,
        "alerta": alerta_disparada,
        "ttl_restante": r.ttl(key),
    }


def obtener_contadores_elevados(r: redis.Redis, umbral: int = UMBRAL_ALERTAS) -> list[dict]:
    """Retorna todos los medicamentos con contador >= umbral en las últimas 24h."""
    keys = r.keys("contador:efectos:*")
    resultado = []
    for key in keys:
        valor = r.get(key)
        if valor and int(valor) >= umbral:
            medicamento_id = key.replace("contador:efectos:", "")
            resultado.append({
                "medicamento_id": medicamento_id,
                "conteo_24h": int(valor),
                "ttl_restante": r.ttl(key),
            })
    return sorted(resultado, key=lambda x: x["conteo_24h"], reverse=True)


if __name__ == "__main__":
    from redis_db.connection import get_redis

    r = get_redis()
    print("=== Control de Acceso y Cola de Evaluación ===\n")

    acceso = otorgar_acceso(r, "ENS001", "INV00789", "investigador", "Hospital Italiano")
    print(f"Acceso otorgado: {acceso}")

    verificacion = verificar_acceso(r, "ENS001", "INV00789")
    print(f"Verificación: {verificacion}")

    encolar_reporte(r, {"medicamento_id": "MED001", "efecto": "cefalea", "severidad": "leve"})
    encolar_reporte(r, {"medicamento_id": "MED002", "efecto": "nauseas", "severidad": "moderada"})
    print(f"\nCola size: {tamanio_cola(r)}")

    reporte = tomar_reporte(r)
    print(f"Reporte tomado: {reporte}")

    for i in range(6):
        res = incrementar_contador_y_alertar(r, "MED003", umbral=5)
    print(f"\nContador MED003: {res['conteo_24h']}  alerta={res['alerta_disparada']}")
