# TP Farmacéutica - Base de Datos 2

Sistema de gestión de información farmacéutica con arquitectura **poliglota** (MongoDB + Neo4j + Redis), expuesto mediante una API REST construida con FastAPI y consumida desde un dashboard expuesto en "/dashboard".

## Requisitos Previos

- **Python 3.11+**
- **Docker y Docker Compose**

Es posible que al instalar Docker también pida instalar WSL 2.


## Instalación

Requiere únicamente **Docker y Docker Compose**.

```bash
# 1. Levantar todos los servicios (bases de datos + API)
docker compose up -d

# 2. Cargar datos de prueba (solo ejecutar la 1ra vez cuando aún no hay datos)
docker compose exec api python seed/generar_datos.py --all --redis-load
```

## Desarrollo

Una vez que ya está en la compu y se quiere levantar el proyecto:

```bash
# Con este comando se levanta todo
docker compose up -d

# Con este otro comando frena todo el proyecto
docker compose down
```

Servicios disponibles:

| Servicio | URL / Puerto |
|---------|-------------|
| MongoDB | `localhost:27017` |
| Mongo Express (UI) | `http://localhost:8081` |
| Neo4j Browser | `http://localhost:7474` (user: `neo4j` / pass: `farmaceutica`) |
| Neo4j Bolt | `localhost:7687` |
| Redis | `localhost:6379` |
| Redis Commander (UI) | `http://localhost:8082` |
| **URL del API** | `http://localhost:8000` |
| **Documentación** | `http://localhost:8000/docs` |

---

## Estructura del Proyecto

```
tp-farmaceutica/
├── mongodb/                    # Capa MongoDB (TP1)
│   ├── connection.py
│   ├── init_indexes.py
│   └── queries/               # Consultas a-e
├── neo4j_db/                  # Capa Neo4j (TP1)
│   ├── connection.py
│   ├── init_constraints.py
│   └── queries/               # Consultas a-e
├── redis_db/                  # Capa Redis (TP2)
│   ├── connection.py          # Cliente configurable por env vars
│   └── queries/
│       ├── a_alertas_farmacovigilancia.py  # SORTED SET
│       ├── b_cadena_frio.py                # STREAM
│       └── c_control_acceso.py            # HASH + LIST + STRING
├── api/                       # API REST poliglota (TP2)
│   ├── main.py                # FastAPI app
│   ├── models.py              # Modelos Pydantic
│   └── routers/
│       ├── op1_panel.py               # GET  /panel
│       ├── op2_prescripcion.py        # POST /prescripcion/verificar
│       ├── op3_trazabilidad.py        # GET  /lote/{numero}/trazabilidad
│       ├── op4_interacciones.py       # GET  /medicamento/{id}/interacciones
│       └── op5_cierre_alerta.py       # POST /alerta/cerrar
├── seed/
│   ├── config.py
│   ├── generar_datos.py       # Script principal
│   ├── datos_maestros.py
│   ├── generador_mongo.py
│   ├── generador_neo4j.py
│   └── generador_redis.py     # Seed para Redis (TP2)
├── docker-compose.yml         # MongoDB + Neo4j + Redis + API
├── Dockerfile                 # Imagen de la API
└── requirements.txt
```

---

## API REST — Capa Poliglota (TP2)

### Endpoints

#### OP-1 — Panel de farmacovigilancia en tiempo real (3 motores)

```
GET /panel
```

Consolida el estado de riesgo del sistema: alertas activas y cola (Redis), medicamentos más reportados del último mes (MongoDB), principios activos más peligrosos (Neo4j).

---

#### OP-2 — Verificación de prescripción (3 motores)

```
POST /prescripcion/verificar
```

```json
{
  "paciente_id": "PAC-2024-00001",
  "medicamento_id": "<ObjectId del medicamento>"
}
```

Detecta interacciones en Neo4j → verifica alertas activas en Redis → recupera historial en MongoDB → si hay riesgo grave, publica alerta en Redis.

---

#### OP-3 — Trazabilidad de lote y cadena de frío (2 motores)

```
GET /lote/{numero_lote}/trazabilidad?vehiculo_id=VEH002
```

Lee el STREAM de temperatura del vehículo (Redis) y si detecta ruptura publica alerta. Retorna también la trazabilidad completa del lote (MongoDB).

---

#### OP-4 — Análisis de interacciones para nuevo medicamento (2 motores)

```
GET /medicamento/{medicamento_id}/interacciones
GET /medicamento/nuevo/interacciones?principios_activos=Amoxicilina&principios_activos=Clavulanato
```

Recupera los principios activos del medicamento (MongoDB) y mapea todas sus interacciones conocidas con medicamentos existentes (Neo4j), ordenadas por severidad.

---

#### OP-5 — Cierre de alerta de farmacovigilancia (3 motores)

```
POST /alerta/cerrar
```

```json
{
  "alerta_id": "ALT-A1B2C3D4",
  "medicamento_id": "MED001",
  "resultado": "confirmado",
  "investigador_id": "INV001",
  "acciones_tomadas": "Suspensión del lote y notificación a ANMAT",
  "nueva_interaccion": {
    "pa1": "Warfarina",
    "pa2": "Ibuprofeno",
    "tipo": "farmacocinetica",
    "severidad": "grave",
    "mecanismo": "Desplazamiento de proteínas plasmáticas"
  }
}
```

Elimina la alerta de Redis (y decrementa contador si es falso positivo) → persiste el dictamen en MongoDB → si se confirmó nueva interacción, la crea en el grafo Neo4j.

---

## Consultas individuales (TP1)

### MongoDB

```bash
PYTHONPATH=. python -m mongodb.queries.a_trazabilidad <numero_lote>
PYTHONPATH=. python -m mongodb.queries.b_lotes_vencimiento
PYTHONPATH=. python -m mongodb.queries.c_efectos_adversos <medicamento_id>
PYTHONPATH=. python -m mongodb.queries.d_ensayos_fase_iii
PYTHONPATH=. python -m mongodb.queries.e_senal_farmacovigilancia
```

### Neo4j

```bash
PYTHONPATH=. python -m neo4j_db.queries.a_interacciones_prescripcion <paciente_id>
PYTHONPATH=. python -m neo4j_db.queries.b_red_principio_activo <nombre_pa>
PYTHONPATH=. python -m neo4j_db.queries.c_toxicidad_acumulativa
PYTHONPATH=. python -m neo4j_db.queries.d_pa_mas_peligroso --top 10
PYTHONPATH=. python -m neo4j_db.queries.e_prediccion_interacciones Amoxicilina Clavulanato
```

### Redis (módulos individuales)

```bash
PYTHONPATH=. python -m redis_db.queries.a_alertas_farmacovigilancia
PYTHONPATH=. python -m redis_db.queries.b_cadena_frio
PYTHONPATH=. python -m redis_db.queries.c_control_acceso
```

### Demo completo (TP1)

```bash
PYTHONPATH=. python run_demo.py
```

---

## Datos generados

| Motor | Entidad | Cantidad |
|-------|---------|----------|
| MongoDB | Principios activos | 80 |
| MongoDB | Medicamentos | 200 |
| MongoDB | Distribuidores | 50 |
| MongoDB | Lotes | 150 |
| MongoDB | Ensayos clínicos | 20 |
| MongoDB | Efectos adversos | 300 |
| Neo4j | `:PrincipioActivo` | 80 |
| Neo4j | `:Medicamento` | 200 |
| Neo4j | `:Patologia` | ~40 |
| Neo4j | `:EnsayoClinico` | 20 |
| Neo4j | `:Paciente` | 50 |
| Redis | Alertas (SORTED SET) | 10 |
| Redis | Lecturas temperatura (STREAM) | 30 (3 vehículos; VEH002 con ruptura) |
| Redis | Reportes pendientes (LIST) | 5 |
| Redis | Accesos a ensayos (HASH) | 4 |
| Redis | Contadores 24h (STRING) | 4 (MED001 y MED003 sobre umbral) |

---

## Verificación

```bash
# MongoDB
mongosh --eval "use farmaceutica_tp; db.medicamentos.countDocuments()"

# Neo4j
cypher-shell -u neo4j -p farmaceutica "MATCH (n) RETURN labels(n), count(n)"

# Redis
redis-cli ZCARD alertas:farmacovigilancia   # cantidad de alertas
redis-cli XLEN temperatura:stream           # lecturas de temperatura
redis-cli LLEN cola:efectos_adversos        # reportes pendientes
```

---

## Detener y limpiar

```bash
# Detener contenedores
docker compose down

# Eliminar datos y reiniciar desde cero
docker compose down -v
docker compose up -d
docker compose exec api python seed/generar_datos.py --all --redis-load
```

---

## Solución de problemas

**Error: "No se pudo conectar a MongoDB"**
```bash
docker compose restart mongodb
```

**Error: "No se pudo conectar a Neo4j"**
```bash
# Neo4j tarda ~30 segundos en iniciar
docker compose logs neo4j
```

**Error: "No se pudo conectar a Redis"**
```bash
docker compose restart redis
redis-cli ping   # debe responder PONG
```

**Error al importar módulos**
```bash
# Siempre ejecutar desde la raíz del proyecto con PYTHONPATH=.
PYTHONPATH=. python -m mongodb.queries.a_trazabilidad
```