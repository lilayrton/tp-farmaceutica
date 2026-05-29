"""
STREAM: temperatura:stream
Campos por entrada: vehiculo_id, temperatura_celsius, latitud, longitud
Rango seguro de temperatura para medicamentos: 2.0 – 8.0 °C
"""
import redis

from redis_db.queries.a_alertas_farmacovigilancia import publicar_alerta

STREAM_KEY = "temperatura:stream"
TEMP_MIN = 2.0
TEMP_MAX = 8.0


def registrar_lectura(
    r: redis.Redis,
    vehiculo_id: str,
    temperatura_celsius: float,
    latitud: float,
    longitud: float,
) -> str:
    """Registra una lectura de temperatura en el STREAM. Retorna el ID de la entrada."""
    entry_id = r.xadd(
        STREAM_KEY,
        {
            "vehiculo_id": vehiculo_id,
            "temperatura_celsius": str(temperatura_celsius),
            "latitud": str(latitud),
            "longitud": str(longitud),
        },
    )
    return entry_id


def obtener_ultimas_lecturas(
    r: redis.Redis,
    vehiculo_id: str,
    n: int = 12,
) -> list[dict]:
    """Retorna las últimas n lecturas del vehículo para análisis de tendencia."""
    # XREVRANGE trae las más recientes primero
    all_entries = r.xrevrange(STREAM_KEY, count=n * 5)
    lecturas = []
    for entry_id, fields in all_entries:
        if fields.get("vehiculo_id") == vehiculo_id:
            lecturas.append(
                {
                    "id": entry_id,
                    "vehiculo_id": fields["vehiculo_id"],
                    "temperatura_celsius": float(fields["temperatura_celsius"]),
                    "latitud": float(fields["latitud"]),
                    "longitud": float(fields["longitud"]),
                }
            )
            if len(lecturas) >= n:
                break
    return lecturas


def detectar_ruptura_cadena_frio(
    r: redis.Redis,
    vehiculo_id: str,
    rango: tuple[float, float] = (TEMP_MIN, TEMP_MAX),
) -> dict:
    """Detecta ruptura de cadena de frío si las últimas 2 lecturas del vehículo
    están fuera del rango. Si hay ruptura, publica alerta automáticamente."""
    temp_min, temp_max = rango
    ultimas = obtener_ultimas_lecturas(r, vehiculo_id, n=12)
    ultimas = ultimas[:2]

    resultado = {
        "vehiculo_id": vehiculo_id,
        "ruptura_detectada": False,
        "lecturas_analizadas": ultimas,
        "rango_seguro": {"min": temp_min, "max": temp_max},
        "alerta_publicada": None,
    }

    if len(ultimas) < 2:
        resultado["mensaje"] = "Insuficientes lecturas para detectar ruptura (mínimo 2)"
        return resultado

    fuera_de_rango = [
        l for l in ultimas if not (temp_min <= l["temperatura_celsius"] <= temp_max)
    ]

    if len(fuera_de_rango) == 2:
        resultado["ruptura_detectada"] = True
        temps = [l["temperatura_celsius"] for l in fuera_de_rango]
        descripcion = (
            f"Ruptura cadena de frío en {vehiculo_id}: "
            f"temperaturas {temps[0]}°C y {temps[1]}°C fuera del rango [{temp_min},{temp_max}]°C"
        )
        alerta = publicar_alerta(
            r,
            medicamento_id=vehiculo_id,
            severidad=5,
            tipo="lote_comprometido",
            descripcion=descripcion,
        )
        resultado["alerta_publicada"] = alerta
        resultado["mensaje"] = descripcion

    return resultado


def consultar_tendencia(r: redis.Redis, vehiculo_id: str) -> list[dict]:
    """Retorna las últimas 12 lecturas de un vehículo para análisis de tendencia."""
    return obtener_ultimas_lecturas(r, vehiculo_id, n=12)


if __name__ == "__main__":
    from redis_db.connection import get_redis

    r = get_redis()
    print("=== Monitoreo Cadena de Frío ===\n")

    registrar_lectura(r, "VEH001", 4.5, -34.6, -58.4)
    registrar_lectura(r, "VEH001", 5.1, -34.7, -58.5)
    registrar_lectura(r, "VEH002", 12.3, -33.4, -60.2)
    registrar_lectura(r, "VEH002", 14.7, -33.5, -60.3)

    print("Tendencia VEH001:")
    for l in consultar_tendencia(r, "VEH001"):
        print(f"  {l['temperatura_celsius']}°C  ({l['latitud']}, {l['longitud']})")

    print("\nDetección ruptura VEH002:")
    res = detectar_ruptura_cadena_frio(r, "VEH002")
    print(f"  Ruptura: {res['ruptura_detectada']}")
    if res["alerta_publicada"]:
        print(f"  Alerta generada: {res['alerta_publicada']['id']}")
