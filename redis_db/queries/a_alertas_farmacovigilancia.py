"""
SORTED SET: alertas:farmacovigilancia
Score = severidad (1-5) × urgencia_mult (1.0-3.0)  →  rango [1.0, 15.0]
Member = JSON con id, medicamento_id, tipo, descripcion, timestamp
"""
import json
import uuid
from datetime import datetime, timezone

import redis

KEY = "alertas:farmacovigilancia"

TIPOS_VALIDOS = {"interaccion_grave", "reaccion_adversa", "lote_comprometido"}
URGENCIA_POR_TIPO = {
    "interaccion_grave": 3.0,
    "reaccion_adversa": 2.0,
    "lote_comprometido": 1.5,
}


def publicar_alerta(
    r: redis.Redis,
    medicamento_id: str,
    severidad: int,
    tipo: str,
    descripcion: str,
) -> dict:
    """Publica una nueva alerta en el SORTED SET con score = severidad × urgencia."""
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de alerta inválido: {tipo}. Válidos: {TIPOS_VALIDOS}")
    if not 1 <= severidad <= 5:
        raise ValueError("severidad debe estar entre 1 y 5")

    alerta_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
    urgencia = URGENCIA_POR_TIPO[tipo]
    score = severidad * urgencia

    alerta = {
        "id": alerta_id,
        "medicamento_id": medicamento_id,
        "tipo": tipo,
        "descripcion": descripcion,
        "severidad": severidad,
        "score": score,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    r.zadd(KEY, {json.dumps(alerta): score})
    return alerta


def consumir_alerta_maxima(r: redis.Redis) -> dict | None:
    """Extrae y retorna la alerta de mayor score (ZPOPMAX)."""
    resultado = r.zpopmax(KEY, count=1)
    if not resultado:
        return None
    member, score = resultado[0]
    alerta = json.loads(member)
    alerta["score_consumido"] = score
    return alerta


def listar_alertas_activas(r: redis.Redis, tipo: str | None = None) -> list[dict]:
    """Lista todas las alertas activas ordenadas por severidad descendente.
    Si se especifica tipo, filtra por ese tipo."""
    entries = r.zrevrange(KEY, 0, -1, withscores=True)
    alertas = []
    for member, score in entries:
        alerta = json.loads(member)
        alerta["score"] = score
        if tipo is None or alerta.get("tipo") == tipo:
            alertas.append(alerta)
    return alertas


def escalar_alerta(r: redis.Redis, alerta_id: str, incremento: float = 1.0) -> float | None:
    """Aumenta el score de una alerta existente (escala la urgencia)."""
    entries = r.zrange(KEY, 0, -1, withscores=True)
    for member, score in entries:
        alerta = json.loads(member)
        if alerta.get("id") == alerta_id:
            nuevo_score = r.zincrby(KEY, incremento, member)
            return nuevo_score
    return None


def eliminar_alerta(r: redis.Redis, alerta_id: str) -> bool:
    """Elimina una alerta por ID (usado en OP-5 cierre de alerta)."""
    entries = r.zrange(KEY, 0, -1)
    for member in entries:
        alerta = json.loads(member)
        if alerta.get("id") == alerta_id:
            r.zrem(KEY, member)
            return True
    return False


if __name__ == "__main__":
    from redis_db.connection import get_redis

    r = get_redis()
    print("=== Sistema de Alertas de Farmacovigilancia ===\n")

    a1 = publicar_alerta(r, "MED001", 5, "interaccion_grave", "Interacción crítica detectada")
    print(f"Alerta publicada: {a1['id']}  score={a1['score']}")

    a2 = publicar_alerta(r, "MED002", 3, "reaccion_adversa", "Reacción adversa moderada")
    print(f"Alerta publicada: {a2['id']}  score={a2['score']}")

    print("\nAlertas activas:")
    for a in listar_alertas_activas(r):
        print(f"  [{a['score']:.1f}] {a['id']} — {a['tipo']} — {a['descripcion']}")

    consumida = consumir_alerta_maxima(r)
    print(f"\nAlerta consumida (máxima): {consumida['id']}  score={consumida['score_consumido']}")
