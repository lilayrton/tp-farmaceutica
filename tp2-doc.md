**INGENIERÍA DE DATOS II**

**TRABAJO PRÁCTICO INTEGRADOR**

2.ª Entrega

**TEMA 13**

**Empresa Farmacéutica \- Medicamentos y Ensayos Clínicos**

# Índice {#índice}

[**Índice	2**](#índice)

[**Introducción	4**](#introducción)

[**Justificación de Redis.	5**](#justificación-de-redis.)

[Problema que MongoDB y Neo4j no resuelven	5](#problema-que-mongodb-y-neo4j-no-resuelven)

[Alternativas evaluadas y descartadas	5](#alternativas-evaluadas-y-descartadas)

[**Modelado en Redis.	6**](#modelado-en-redis.)

[Convenciones de nombre de clave.	6](#convenciones-de-nombre-de-clave.)

[Estructuras de datos por caso de uso.	6](#estructuras-de-datos-por-caso-de-uso.)

[Score compuesto para alertas.	6](#score-compuesto-para-alertas.)

[TTL por rol de acceso.	7](#ttl-por-rol-de-acceso.)

[Datos de prueba.	7](#datos-de-prueba.)

[**Diseño de la Capa Políglota.	8**](#diseño-de-la-capa-políglota.)

[Tabla de responsabilidades por motor.	8](#tabla-de-responsabilidades-por-motor.)

[Estructura del proyecto.	8](#estructura-del-proyecto.)

[Interfaz de la aplicación: API REST	9](#interfaz-de-la-aplicación:-api-rest)

[Infraestructura	9](#infraestructura)

[Diagramas de flujo de datos por operación	9](#diagramas-de-flujo-de-datos)

[**Operaciones Políglotas	10**](#operaciones-políglotas)

[OP-1: Panel de farmacovigilancia en tiempo real (3 motores)	10](#op-1:-panel-de-farmacovigilancia-en-tiempo-real-\(3-motores\))

[Flujo de consultas implementado:	10](#flujo-de-consultas-implementado:)

[OP-2: Verificación de prescripción y detección de riesgos (3 motores)	10](#op-2:-verificación-de-prescripción-y-detección-de-riesgos-\(3-motores\))

[Flujo de consultas implementado:	11](#flujo-de-consultas-implementado:-1)

[OP-3: Trazabilidad de lote y alerta de ruptura de cadena de frío (2 motores)	11](#op-3:-trazabilidad-de-lote-y-alerta-de-ruptura-de-cadena-de-frío-\(2-motores\))

[Flujo de consultas implementado:	11](#flujo-de-consultas-implementado:-2)

[¿Por qué no usamos Neo4j?	12](#¿por-qué-no-usamos-neo4j?)

[OP-4: Análisis de interacciones para un nuevo medicamento (2 motores)	12](#op-4:-análisis-de-interacciones-para-un-nuevo-medicamento-\(2-motores\))

[Flujo de consultas implementado:	12](#flujo-de-consultas-implementado:-3)

[¿Por qué no usamos Redis?	12](#¿por-qué-no-usamos-redis?)

[OP-5: Cierre de alerta de farmacovigilancia (3 motores)	12](#op-5:-cierre-de-alerta-de-farmacovigilancia-\(3-motores\))

[Flujo implementado: generación → evaluación → resolución	12](#flujo-implementado:-generación-→-evaluación-→-resolución)

[**Coherencia entre Motores	14**](#coherencia-entre-motores)

[El problema de la coherencia distribuida	14](#el-problema-de-la-coherencia-distribuida)

[6.2 Patrón implementado: escrituras independientes con registro de errores	14](#heading=)

[6.3 Orden de escritura y justificación	14](#heading=)

[6.4 Garantías que ofrece el sistema y cuáles no	14](#heading=)

[**Comparación con Arquitectura Puramente Relacional	16**](#comparación-con-arquitectura-puramente-relacional)

[Operación seleccionada: OP-2: Verificación de prescripción	16](#operación-seleccionada:-op-2:-verificación-de-prescripción)

[Solución SQL equivalente	16](#solución-sql-equivalente)

[7.3 Análisis comparativo	16](#7.3-análisis-comparativo)

[7.4 Conclusión de la comparación	17](#7.4-conclusión-de-la-comparación)

[**Conclusiones	18**](#conclusiones)

[¿Qué ganó el sistema?	18](#¿qué-ganó-el-sistema?)

[¿Qué complejidad adicional introdujo?	18](#¿qué-complejidad-adicional-introdujo?)

[**Bibliografía	19**](#bibliografía)

[Obligatoria — incorporada en esta entrega	19](#heading=)

[Complementaria	19](#heading=)

[Documentación oficial — toda la entrega	19](#documentación-oficial-—-toda-la-entrega)

# Introducción {#introducción}

Esta segunda entrega extiende el sistema de persistencia diseñado en la primer entrega. El sistema ya implementado cubre el catálogo de medicamentos, trazabilidad de lotes y ensayos clínicos en MongoDB, más la red de interacciones entre principios activos en Neo4j. La presente entrega incorpora dos nuevas cuestiones que completan la arquitectura políglota:

* **Tercer motor (Redis)**: incorporación de Redis para gestionar alertas de farmacovigilancia en tiempo real (SORTED SET), monitoreo de temperatura de la cadena de frío (STREAM), cola de evaluación de reportes de efectos adversos (LIST), control de acceso temporal a ensayos clínicos (HASH+TTL) y contadores de señal de farmacovigilancia con ventana deslizante de 24h (STRING+EXPIRE).  
* **Capa de persistencia políglota**: API REST construida con FastAPI que integra los tres motores en 5 operaciones de negocio cohesivas. Cada endpoint decide explícitamente qué datos consulta en cada motor y cómo ensambla la respuesta.

La aplicación se estructura como una API REST con documentación Swagger disponible en /docs, que permite ejecutar las 5 operaciones políglotas sin modificar el código. Las conexiones a los tres motores se configuran mediante las variables de entorno necesarias.

# Justificación de Redis. {#justificación-de-redis.}

## Problema que MongoDB y Neo4j no resuelven {#problema-que-mongodb-y-neo4j-no-resuelven}

La arquitectura de la primera entrega cubre dos aspectos. MongoDB gestiona el catálogo  heterogéneo de medicamentos, trazabilidad embebida de lotes y farmacovigilancia histórica. Neo4j modela la red de interacciones entre principios activos con traversal nativo de grafos. Sin embargo, el dominio farmacéutico tiene un tercer aspecto que ninguno de los dos resuelve eficientemente: los datos operativos en tiempo real.

Las alertas de farmacovigilancia deben atenderse en horas. Los sensores de temperatura de vehículos refrigerados reportan cada pocos minutos. La cola de reportes de afectos adversos pendientes de evaluación médica crece y se consume de forma concurrente. El acceso a datos de ensayos clínicos expira automáticamente según el rol (investigador: 8hs, auditor: 4hs, regulador: 24hs).

Redis se incorpora porque el dominio farmacéutico tiene datos que son naturalmente temporales, de alta frecuencia y requieren operaciones atómicas. Las cinco estructuras de datos nativas de Redis (SORTED SET, STREAM, LIST, HASH, STRING con EXPIRE) mapean directamente a los cinco casos de uso operativos necesarios. Como señala **Harrison (2015)**, la persistencia políglota se justifica cuando cada motor hace algo que los demás no pueden hacer bien.

## Alternativas evaluadas y descartadas {#alternativas-evaluadas-y-descartadas}

| Alternativa | Motivo de descarte |
| ----- | ----- |
| **MongoDB con TTL indexes** | Podría implementar colas y contadores con expiración automática mediante TTL indexes, pero requiere procesos de limpieza periódica y no ofrece atomicidad garantizada para consumo concurrente (no existe equivalente a ZPOPMAX o LPUSH/RPOP atómicos). La latencia submilisegundo de Redis para datos en memoria es inalcanzable con MongoDB en disco. |
| **Neo4j con nodos de estado** | Neo4j no está diseñado para datos operativos que varían mucho. Crear y eliminar nodos de alta frecuencia saturaría el grafo y degradaría el rendimiento de los traversals relacionales que justifican su uso.|
| **Redis como caché de MongoDB** | Error conceptual frecuente. En este sistema Redis no cachea datos de MongoDB, sino que es la fuente de verdad para el estado operativo en tiempo real. Lo que vive en Redis (alertas activas, temperatura actual, accesos vigentes) todavía no existe en MongoDB. |

# Modelado en Redis. {#modelado-en-redis.}

## Convenciones de nombre de clave. {#convenciones-de-nombre-de-clave.}

Todas las claves siguen el patrón entidad:identificador:atributo indicadas en las consignas.

| alertas:farmacovigilancia         → SORTED SET  — alertas activas ordenadas por score |
| :---- |
| temperatura:stream                → STREAM       — log inmutable de lecturas de temperatura |
| cola:efectos\_adversos             → LIST         — reportes FIFO pendientes de evaluación |
| acceso:ensayo:{ens\_id}:{inv\_id}   → HASH+TTL     — permisos de acceso con vencimiento |
| contador:efectos:{med\_id}         → STRING+EXPIRE — contador de reportes en ventana 24h |

## Estructuras de datos por caso de uso. {#estructuras-de-datos-por-caso-de-uso.}

| SORTED SET | alertas:farmacovigilancia | Cola de alertas activas ordenadas por score compuesto (severidad × urgencia\_por\_tipo) | ZADD al publicar (`publicar_alerta()`). ZPOPMAX (`consumir_alerta_maxima()`) para consumo ciego de la alerta de mayor score sin conocer su ID. ZREVRANGE (`listar_alertas_activas()`) para listar ordenadas sin eliminar. ZINCRBY (`escalar_alerta(alerta_id, incremento)`) para aumentar el score de una alerta existente si se confirma el riesgo. ZREM (`eliminar_alerta(alerta_id)`) para eliminar una alerta específica por ID en OP-5. Filtrado por tipo: ZREVRANGE WITHSCORES + filter en Python por `json.loads(member)['tipo'] == tipo_buscado`. |
| :---- | :---- | :---- | :---- |
| STREAM | temperatura:stream | Log inmutable de lecturas de temperatura: vehiculo\_id, temperatura\_celsius, latitud, longitud | XADD al registrar. XREVRANGE para obtener últimas lecturas por vehículo. Detección de ruptura sobre 2 lecturas consecutivas fuera de rango \[2°C, 8°C\]. |
| LIST | cola:efectos\_adversos | Cola FIFO de reportes de efectos adversos pendientes de evaluación médica | LPUSH al recibir reporte. RPOP cuando el médico toma el caso. LLEN para tamaño de cola en OP-1. |
| HASH \+ TTL | acceso:ensayo:{ens}:{inv} | Control de acceso temporal a ensayos clínicos: investigador\_id, rol, institución, permisos, timestamp | HSET \+ EXPIRE al otorgar. HGETALL \+ TTL para verificar. EXPIRE automático revoca el acceso sin código adicional. |
| STRING \+ EXPIRE | contador:efectos:{med\_id} | Contador de reportes adversos por medicamento en ventana deslizante de 24 horas | INCR atómico. EXPIRE de 86400s en creación. DECR en OP-5 si resultado es falso\_positivo. KEYS para listar sobre umbral. |

## Justificación de estructuras elegidas. {#justificación-de-estructuras-elegidas.}

**SORTED SET vs LIST para alertas de farmacovigilancia**

Una LIST implementa una cola FIFO estricta: el primer reporte que entra es el primero en salir. Para la cola de efectos adversos eso es lo adecuado, porque los reportes se procesan en orden de llegada. Sin embargo, las alertas de farmacovigilancia no tienen una misma prioridad: una interacción grave con severidad 5 debe atenderse antes que una reacción leve con severidad 1, independientemente de cuándo llegaron. El SORTED SET resuelve este problema de forma nativa: ZADD asigna un score compuesto (severidad × urgencia\_por\_tipo) y ZPOPMAX devuelve atómicamente la alerta de mayor riesgo. En una LIST esto requeriría recorrer toda la cola para encontrar el elemento de mayor prioridad (O(n)), sin garantía de atomicidad en entornos concurrentes. El SORTED SET lo hace en O(log n) con atomicidad garantizada por el motor.

**STREAM vs SORTED SET para el log de temperatura**

Un SORTED SET ordena por score pero no preserva el orden de inserción ni el timestamp original: dos lecturas del mismo vehículo con temperatura exactamente igual tendrían el mismo score y Redis las ordenaría arbitrariamente. Más importante, SORTED SET no admite múltiples lecturas del mismo vehículo con el mismo valor de temperatura sin colisión de clave. El STREAM, en cambio, es un log inmutable que garantiza orden total sin duplicados (mediante un ID `timestamp-secuencia`). Esto permite detectar rupturas comparando lecturas consecutivas del mismo vehículo con XREVRANGE, implementar ventanas temporales sin proceso de limpieza y auditar el historial completo de temperaturas. El STREAM es la mejor opción para datos de series temporales pero el SORTED SET es la estructura indicada para gestionar prioridades.

## Score compuesto para alertas. {#score-compuesto-para-alertas.}

El módulo a\_alertas\_farmacovigilancia.py implementa el score como severidad x urgencia\_por\_tipo, donde urgencia\_por\_tipo es un multiplicador según el tipo de alerta:

| URGENCIA\_POR\_TIPO \= { |
| :---- |
|     'interaccion\_grave': 3.0,   \# score máximo: 5 × 3.0 \= 15.0 |
|     'reaccion\_adversa':  2.0,   \# score máximo: 5 × 2.0 \= 10.0 |
|     'lote\_comprometido': 1.5,   \# score máximo: 5 × 1.5 \=  7.5 |
| } |
| score \= severidad \* urgencia  \# float en rango \[1.0, 15.0\] |

Este diseño garantiza que ZPOPMAX siempre devuelva la interacción grave más urgente antes que una reacción adversa de igual severidad, ya que su multiplicador es mayor. Dentro del mismo tipo, la severidad (1-5) discrimina el orden de atención.

## TTL por rol de acceso. {#ttl-por-rol-de-acceso.}

El módulo c\_control\_acceso.py implementa tres TTL según el rol, respetando exactamente los requerimientos de la consigna:

| TTL\_POR\_ROL \= { |
| :---- |
|     'investigador': 28800,  \# 8 horas |
|     'auditor':      14400,  \# 4 horas |
|     'regulador':    86400,  \# 24 horas |
| } |

## Datos de prueba. {#datos-de-prueba.}

Se desarrolló un módulo seed/generador\_redis.py para poblar las cinco estructuras con datos representativos del dominio. Este proceso garantiza la generación de un dataset coherente con los datos ya cargados en los motores anteriores.

| Estructura | Cantidad seed | Garantía de prueba |
| ----- | ----- | ----- |
| SORTED SET | 10 alertas | Alertas de todos los tipos y severidades. MED001 y MED006 con severidad 5\. |
| STREAM | 30 lecturas | 3 vehículos × 10 lecturas. VEH002 tiene ruptura: últimas 2 lecturas entre 10°C y 18°C, fuera del rango \[2, 8\]°C. |
| LIST | 5 reportes | Reportes con gravedades leve, moderada y grave. Orden FIFO preservado. |
| HASH+TTL | 4 accesos | Un investigador, un auditor y dos roles variados. TTL según rol. |
| STRING+EXPIRE | 4 contadores | MED001 con conteo=8 y MED003 con conteo=6, ambos sobre el umbral=5 para activar alertas en OP-1. |

# Diseño de la Capa Políglota. {#diseño-de-la-capa-políglota.}

## Tabla de responsabilidades por motor. {#tabla-de-responsabilidades-por-motor.}

| Motor | Responsabilidad | Datos que gestiona | Módulo(s) del proyecto |
| ----- | ----- | ----- | ----- |
| MongoDB | Fuente de verdad histórica | Catálogo de medicamentos (200 docs), lotes con trazabilidad embebida (150), ensayos clínicos (20), efectos adversos (300), distribuidores (50), dictámenes de alertas cerradas. | mongodb/connection.py, mongodb/queries/a-e |
| Neo4j | Red de relaciones y grafos | Red de interacciones entre principios activos (200+ relaciones INTERACTUA\_CON), detección de combinaciones peligrosas, predicción de interacciones para nuevos medicamentos. | neo4j\_db/connection.py, neo4j\_db/queries/a-e |
| Redis | Estado operativo en tiempo real | Alertas activas de farmacovigilancia, log de temperatura de cadena de frío, cola FIFO de evaluación de reportes, control de acceso temporal a ensayos, contadores de 24h. | redis\_db/connection.py, redis\_db/queries/a-c |

## Estructura del proyecto. {#estructura-del-proyecto.}

El proyecto sigue una arquitectura en capas con separación clara entre acceso a datos y lógica de negocio:

| tp-farmaceutica/ |
| :---- |
| ├── mongodb/                    \# Capa MongoDB (TP1) |
| │   ├── connection.py           \# Cliente configurable por env vars |
| │   ├── init\_indexes.py         \# 4 índices compuestos |
| │   └── queries/               \# Consultas a-e como módulos ejecutables |
| ├── neo4j\_db/                  \# Capa Neo4j (TP1) |
| │   ├── connection.py |
| │   ├── init\_constraints.py    \# Constraints de unicidad \+ índices |
| │   └── queries/               \# Consultas a-e como módulos ejecutables |
| ├── redis\_db/                  \# Capa Redis (TP2) |
| │   ├── connection.py          \# Singleton configurable por env vars |
| │   └── queries/ |
| │       ├── a\_alertas\_farmacovigilancia.py  \# SORTED SET |
| │       ├── b\_cadena\_frio.py               \# STREAM |
| │       └── c\_control\_acceso.py            \# HASH \+ LIST \+ STRING |
| ├── api/                       \# API REST poliglota (TP2) |
| │   ├── main.py                \# FastAPI app con lifespan \+ health check |
| │   ├── models.py              \# Modelos Pydantic de request |
| │   ├── saga.py                \# Orquestador Saga (compensaciones multi-motor) |
| │   └── routers/ |
| │       ├── op1\_panel.py               \# GET  /panel |
| │       ├── op2\_prescripcion.py        \# POST /prescripcion/verificar |
| │       ├── op3\_trazabilidad.py        \# GET  /lote/{numero}/trazabilidad |
| │       ├── op4\_interacciones.py       \# GET  /medicamento/{id}/interacciones |
| │       └── op5\_cierre\_alerta.py       \# POST /alerta/cerrar |
| ├── seed/                      \# Generador de datos de prueba |
| │   ├── generar\_datos.py       \# Orquestador |
| │   ├── generador\_redis.py     \# Seed específico para Redis (TP2) |
| │   └── ... |
| ├── docker-compose.yml         \# MongoDB 7 \+ Neo4j 5 \+ Redis 7 |
| └── requirements.txt           \# pymongo, neo4j, redis, fastapi, uvicorn |

## Interfaz de la aplicación: API REST {#interfaz-de-la-aplicación:-api-rest}

Se eligió la modalidad de API REST con FastAPI porque cumple los requisitos de la consigna.

* Las operaciones son invocables sin modificar el código: cada endpoint es accesible via HTTP desde el dashboard web.  
* Errores descriptivos: cada router envuelve las llamadas a cada motor en bloques try/except independientes. Los errores se agregan al campo errores: {} de la respuesta JSON sin interrumpir los demás motores.  
* Verificación de conectividad al arrancar: el lifespan de FastAPI en [main.py](http://main.py) hace ping a los tres motores al iniciar y reporta en consola cuáles están disponibles.

## Infraestructura {#infraestructura}

Decidimos utilizar Docker Compose como facilitador del setup del proyecto. El archivo docker-compose.yml levanta los tres motores con un único comando (docker compose up \-d). Cada servicio tiene healthcheck configurado:

| Servicio | Imagen | Puerto(s) | Healthcheck |
| ----- | ----- | ----- | ----- |
| MongoDB | mongo:7 | 27017 \+ Mongo Express en 8081 | mongosh \--eval db.adminCommand('ping') |
| Neo4j | neo4j:5 | 7474 (Browser) \+ 7687 (Bolt) | cypher-shell RETURN 1 |
| Redis | redis:7-alpine | 6379 | redis-cli ping |

Los datos persisten en volúmenes Docker (mongo\_data, neo4j\_data, redis\_data). Redis usa \- \- appendonly yes para durabilidad AOF.

## Diagramas de flujo de datos por operación {#diagramas-de-flujo-de-datos}

### OP-1: Panel de farmacovigilancia (3 motores) — GET /panel

```
Cliente HTTP
     │
     ▼
 GET /panel
     │
     ├─────────────────────────────────────────────────────────────────┐                      │
     │                              │                                   │
     ▼                              ▼                                   ▼
  Redis                          MongoDB                             Neo4j
  ─────                          ───────                             ─────
  ZREVRANGE → top 5 alertas      Aggregation pipeline               MATCH PA
  LLEN → tamaño cola             reportes último mes                interacciones graves
  KEYS+GET → contadores >umbral  top 10 medicamentos                top 5 PA por grado
     │                              │                                   │
     └──────────────────────────────┴───────────────────────────────────┘
                                    │
                                    ▼
                      JSON: { redis: {alertas, cola, contadores},
                               mongodb: {medicamentos},
                               neo4j: {principios_activos},
                               errores: {} }
```

*Cada motor se consulta en bloque try/except independiente. El panel siempre responde aunque un motor falle.*

### OP-2: Verificación de prescripción (3 motores) — POST /prescripcion/verificar

```
Request: { paciente_id, medicamento_id }
     │
     ▼
  0. MongoDB (paso previo)
     Buscar medicamento → extraer principios_activos (nombres + ObjectIds)
     │
     ▼
  1. Neo4j  ──────────────────────────────────────────────────────────────────────────────────
     MATCH paciente→TOMA→med→CONTIENE→pa_existente                                          │
     UNWIND pa_del_nuevo × pa_actuales                                                       │
     MATCH (pa_nuevo)-[i:INTERACTUA_CON]-(pa_existente)                                     │
     ¿hay_grave?                                                                             │
     │                                                                                        │
     ├── sí ──┐                                                                              │
     │        ▼                                                                              │
  2. Redis (lectura)                                                                         │
     ZREVRANGE filtrando por medicamento_id                                                  │
     alertas activas del medicamento                                                         │
     │                                                                                        │
     ▼                                                                                        │
  3. MongoDB                                                                                 │
     Medicamentos con ≥1 PA en común → efectos_adversos                                     │
     del grupo farmacológico en los últimos 6 meses                                         │
     │                                                                                        │
     ▼                                                                                        │
  4. Redis (escritura condicional)  ←─────────────────────────────────────────────────────────┘
     Si hay_grave: publicar_alerta() → ZADD con severidad=5, tipo=interaccion_grave
     │
     ▼
  JSON: { interacciones, alertas_activas, historial_efectos_adversos_grupo,
          riesgo_alto: (hay_grave OR len(alertas)>0), errores: {} }
```

*El paso 0 MongoDB es prerrequisito: provee los PAs del nuevo medicamento que Neo4j necesita para cruzar con los meds actuales del paciente.*

### OP-3: Trazabilidad de lote (2 motores) — GET /lote/{numero\_lote}/trazabilidad

```
Request: numero_lote + vehiculo_id
     │
     ├────────────────────────────┐
     │                            │
     ▼                            ▼
  Redis                        MongoDB
  ─────                        ───────
  XREVRANGE → últimas           $match numero_lote (O(1) con índice único)
  lecturas del vehículo         $project cadena_distribucion embebida
  detectar_ruptura()
  Si ruptura: publicar_alerta()
  ZREVRANGE → últimas 12
  para tendencia
     │                            │
     └────────────────────────────┘
                    │
                    ▼
       JSON: { ruptura_detectada, alerta_publicada,
               tendencia_temperatura, trazabilidad_lote }
```

### OP-4: Análisis de interacciones (2 motores) — GET /medicamento/{id}/interacciones

```
Request: medicamento_id (o principios_activos[])
     │
     ├──────────────────────────┐
     │                          │
     ▼                          ▼
  MongoDB                    Neo4j (depende del resultado de MongoDB)
  ───────                    ─────
  Buscar medicamento          MATCH PA_nuevo→INTERACTUA_CON→PA_existente
  Extraer principios_activos  WHERE pa_existente NOT IN pa_del_nuevo
  del documento               MATCH med_existente→CONTIENE→pa_existente
                              ORDER BY severidad DESC
     │                          │
     └──────────────────────────┘
                    │
                    ▼
       JSON: { interacciones[], resumen_por_severidad{} }
```

### OP-5: Cierre de alerta (3 motores) — POST /alerta/cerrar

```
Request: { alerta_id, medicamento_id, resultado, investigador_id,
           acciones_tomadas, nueva_interaccion? }
     │
     ▼
  SagaOrchestrator()   ← registra compensaciones en orden LIFO
     │
     ▼
  1. Redis  ──────────────── Acción: consumir_alerta_maxima() → ZPOPMAX
     saga.register(         Compensación: ZADD con score original
       _compensar_restaurar_alerta)
     Si resultado='falso_positivo':
       DECR contador:efectos:{med_id}
       saga.register(_compensar_restaurar_contador)
     │
     ▼
  2. MongoDB  ────────────── Acción: insert_one en dictamenes_alertas
     saga.register(         Compensación: delete_one por _id insertado
       _compensar_borrar_dictamen)
     │
     ▼
  3. Neo4j  (solo si resultado='confirmado' Y nueva_interaccion presente)
     ────────────────────── Acción: MERGE (pa1)-[i:INTERACTUA_CON]-(pa2)
     saga.register(         Compensación: DELETE i  (solo si ON CREATE)
       _compensar_borrar_interaccion)
     │
     ▼
  JSON: { alerta_id, resultado, redis, mongodb, neo4j }

  ══════ Si cualquier paso lanza excepción ══════
     │
     ▼
  saga.compensate_all()   ← ejecuta compensaciones en orden inverso
     3. DELETE interacción Neo4j (si fue creada nueva)
     2. delete_one dictamen MongoDB
     1. ZADD alerta de vuelta en Redis  /  INCR contador
     │
     ▼
  JSON: { error, saga: "compensación ejecutada", errores_compensacion? }
```

*OP-5 usa Saga Orquestada porque ZPOPMAX es destructivo: si MongoDB falla después de consumir la alerta, sin compensación la alerta desaparece sin dejar rastro.*

# Operaciones Políglotas {#operaciones-políglotas}

Se implementan las 5 operaciones que integran los motores. Las operaciones OP-1, OP-2 y OP-5 usan los tres motores simultáneamente en una sola respuesta.

## OP-1: Panel de farmacovigilancia en tiempo real (3 motores) {#op-1:-panel-de-farmacovigilancia-en-tiempo-real-(3-motores)}

Endpoint: GET /panel

El equipo de farmacovigilancia necesita una vista unificada del estado de riesgo del sistema. Los tres motores se consultan en bloques try/except independientes para garantizar que el panel siempre responda aunque un motor falle.

### Flujo de consultas implementado: {#flujo-de-consultas-implementado:}

1. **Redis**  
   listar\_alertas\_activas() → ZREVRANGE 0 \- 1 WITHSCORES, se toman las primeras 5\. tamanio\_cola() → LLEN.  
   obtener\_contadores\_elevados(umbral=5) → KEYS contador:efectos:\* \+ GET de cada clave.  
2. **MongoDB**  
   Aggregation pipeline sobre efectos\_adversos: $match por fecha \>= 30 días atrás, $group por medicamento\_id con $sum:1, $sort descendente, $limit 10, $lookup con medicamentos para obtener nombre\_comercial.  
3. **Neo4j**  
   MATCH (pa:PrincipioActivo) \- \[i:INTERACTUA\_CON\] \- (:PrincipioActivo) WHERE i.severidad IN \[‘grave’, ‘contraindicada’\] WITH pa, count(i) AS total ORDER BY total DESC LIMIT 5\.  
4. **Resultado**  
   El endpoint agrega los tres resultado en un único objeto JSON con claves redis, mongodb, neo4j y un campo opcional de errores por si algún motor no respondió.

| Motor | Dato consultado |
| ----- | ----- |
| Redis | Top 5 alertas \+ tamaño cola \+ contadores \> umbral |
| MongoDB | Top 10 medicamentos con más reportes (último mes) |
| Neo4j | Top 5 principios activos con interacciones graves |

**Tiempo de respuesta esperado:** Redis responde en menos de 1 ms (operaciones en memoria). MongoDB ejecuta el aggregation pipeline con el índice idx\_ea\_med\_gravedad\_fecha en aproximadamente 50 ms para el volumen de datos de prueba. Neo4j recorre el grafo de interacciones con el índice sobre PrincipioActivo en aproximadamente 80-100 ms. Las tres consultas se ejecutan de forma secuencial en el código actual, con un tiempo total esperado inferior a 200 ms en condiciones normales de carga. El panel siempre responde aunque un motor falle: los errores de cada motor quedan registrados en el campo errores de la respuesta.

## OP-2: Verificación de prescripción y detección de riesgos (3 motores) {#op-2:-verificación-de-prescripción-y-detección-de-riesgos-(3-motores)}

Endpoint: POST /prescripcion/verificar

Request body: {"paciente\_id": "PAC-2024-00001", "medicamento\_id": "\<ObjectId\>"}

### Flujo de consultas implementado: {#flujo-de-consultas-implementado:-1}

0. **MongoDB (paso previo)**  
   `_mongo_pa_del_medicamento(medicamento_id)` recupera el documento del medicamento a prescribir y extrae los nombres e IDs de sus principios activos. Este paso es necesario para que Neo4j pueda buscar interacciones con los PAs del medicamento nuevo.  
1. **Neo4j**  
   `_neo4j_interacciones_prescripcion(paciente_id, pa_del_nuevo)`: dado el listado de PAs del medicamento a prescribir, hace MATCH del paciente a través de TOMA → CONTIENE → PrincipioActivo para obtener los PAs de los medicamentos que ya toma. Luego cruza ambos conjuntos buscando INTERACTUA\_CON entre los PAs del nuevo y los del paciente. Ordena por severidad descendente (contraindicada → grave → moderada → leve).  
2. **Redis (lectura)**  
   listar\_alertas\_activas() filtrando por medicamento\_id del request.  
   Devuelve solo las alertas que corresponden al medicamento a prescribir.  
3. **MongoDB**  
   `_mongo_historial_efectos_grupo(pa_oids)`: busca en la colección `medicamentos` todos los documentos que comparten al menos un principio activo con el medicamento a prescribir, luego agrega los efectos adversos de ese grupo farmacológico en los últimos 6 meses (limit 10, orden descendente por fecha). Esto provee evidencia poblacional del grupo, no solo del medicamento exacto.  
4. **Redis (escritura condicional)**  
   Si Neo4j detectó alguna interacción con severidad ‘grave’ o ‘contraindicada’, publicar\_alerta() hace ZADD con severidad=5, tipo=interaccion\_grave y descripción contextualizada con paciente\_id y medicamento\_id.  
   

El orden de las consultas es fundamental: el paso previo MongoDB obtiene los PAs del medicamento nuevo, que son el input de Neo4j. Neo4j se ejecuta antes que Redis porque su resultado condiciona la escritura en Redis. MongoDB (historial) se consulta al final porque su resultado no condiciona ninguna escritura, solo enriquece la respuesta.

**Si los tres motores detectan riesgo simultáneamente:** no hay contradicción entre los motores, sino acumulación de evidencia. Neo4j confirma una interacción directa entre los PAs del nuevo medicamento y los del paciente (conocimiento estructural del grafo), Redis informa que ya hay una alerta activa sobre ese medicamento (estado operativo en tiempo real) y MongoDB muestra antecedentes del grupo farmacológico al que pertenece el medicamento (evidencia poblacional de efectos adversos en medicamentos similares). En este caso el sistema: (a) devuelve `riesgo_alto: true`; (b) publica la nueva alerta en el SORTED SET con severidad máxima; (c) incluye los tres bloques de evidencia en la respuesta JSON bajo las claves `interacciones`, `alertas_activas` y `historial_efectos_adversos_grupo_farmacologico`.

Campo riesgo\_alto en la respuesta: True si hay\_grave (Neo4j detectó interacción contraindicada/grave) OR len(alertas\_activas) \> 0 (Redis tiene alertas sobre ese medicamento).

## OP-3: Trazabilidad de lote y alerta de ruptura de cadena de frío (2 motores) {#op-3:-trazabilidad-de-lote-y-alerta-de-ruptura-de-cadena-de-frío-(2-motores)}

Endpoint: GET /lote/{numero\_lote}/trazabilidad?vehiculo\_id=VEH001

### Flujo de consultas implementado: {#flujo-de-consultas-implementado:-2}

1. **Redis**  
   obtener\_ultimas\_lecturas(vehiculo\_id, n=2) usa XREVRANGE temperatura:stream con count=nx5 para filtrar por vehiculo\_id hasta encontrar las 2 más recientes.  
   detectar\_ruptura\_cadena\_frio() verifica si ambas están fuera del rango \[2°C, 8°C\]. Si ruptura=True, llama a publicar\_alerta() con severidad=5 y tipo=lote\_comprometido.  
   consultar\_tendencia() devuelve las últimas 12 lecturas para análisis visual.  
2. **MongoDB**  
   trazabilidad\_lote() ejecuta el pipeline de $match por numero\_lote (usa índice único idx\_lotes\_numero, O(1)) \+ $project con cadena\_distribucion embebida.  
   Devuelve el historial completo desde planta hasta el último punto de dispensación sin JOINs.  
   

### ¿Por qué no usamos Neo4j? {#¿por-qué-no-usamos-neo4j?}

La trazabilidad de un lote es una estructura lineal y jerárquica: planta → distribuidor → farmacia. Esta cadena está embebida como array en el documento del lote en MongoDB (`cadena_distribucion`), lo que permite recuperarla en una sola lectura sin JOINs. Esta consulta no requiere traversal de grafo complejo: simplemente con el $match sobre numero_lote con índice único es O(1). Neo4j modela interacciones entre principios activos, no la cadena física de lotes. Incluirlo en esta operación no agregaría valor.

## OP-4: Análisis de interacciones para un nuevo medicamento (2 motores) {#op-4:-análisis-de-interacciones-para-un-nuevo-medicamento-(2-motores)}

Endpoints: GET /medicamento/{medicamento\_id}/interacciones

También acepta: GET /medicamento/nuevo/interacciones?principios\_activos=Amoxicilina\&principios\_activos=Clavulanato

### Flujo de consultas implementado: {#flujo-de-consultas-implementado:-3}

1. **MongoDB**  
   Si `medicamento_id` es un ObjectId válido, busca el documento en medicamentos, extrae el array `principios_activos` por `_id` para obtener el nombre. El resultado es la lista de nombres de PA del medicamento.
2. **Neo4j**  
   prediccion\_interacciones(pa\_del\_nuevo) ejecuta la consulta 3.5.e de la primera entrega: MATCH (pa\_nuevo:PrincipioActivo) \- \[i:INTERACTUA\_CON\] \- (pa\_existente) WHERE NOT pa\_existente.nombre IN pa\_del\_nuevo MATCH (med\_existente: Medicamento) \- \[:CONTIENE\] \-\> (pa\_existente) WHERE med\_existente.estado=’activo’.  
   Ordena por severidad descendente.  
   

La respuesta incluye resumen\_por\_severidad que agrupa la cantidad de interacciones detectadas por nivel (contraindicada, grave, moderada, leve), facilitando la evaluación regulatoria.

### ¿Por qué no usamos Redis? {#¿por-qué-no-usamos-redis?}

Redis gestiona datos operativos efímeros en tiempo real: alertas activas, colas de evaluación, accesos con TTL y contadores de ventana deslizante. El análisis de interacciones para un nuevo medicamento es una consulta de conocimiento estructural sobre el grafo de principios activos: requiere recorrer relaciones persistentes con propiedades (tipo, severidad, mecanismo) que viven en Neo4j. Redis no almacena el grafo de interacciones ni el catálogo de medicamentos; intentar resolver esta operación con Redis implicaría duplicar en él un subconjunto del grafo de Neo4j, generando inconsistencia y duplicación sin ninguna ganancia de velocidad relevante para una operación que no es de tiempo real.

El análisis de interacciones para un medicamento es una consulta de conocimiento estructural sobre el grafo de principios activos. El medicamento aún no está en el mercado, por lo que hasta el momento no tiene alertas activas en Redis ni contadores de efectos adversos. Usar Redis forzaría una consulta que devolvería vacío, agregando complejidad sin agregar valor.

## OP-5: Cierre de alerta de farmacovigilancia (3 motores) {#op-5:-cierre-de-alerta-de-farmacovigilancia-(3-motores)}

Endpoint: POST /alerta/cerrar

### Flujo implementado: generación → evaluación → resolución {#flujo-implementado:-generación-→-evaluación-→-resolución}

1. **Generación (Redis)**  
   La alerta vive en SORTED SET con su score compuesto:  
   ZADD alertas:farmacovigilancia score payload  
2. **Visualización (Redis OP-1)**  
   El médico ve la alerta en el panel:  
   ZREVRANGE → top 5 alertas activas  
3. **Consumo (Redis)**  
   La alerta de mayor score es extraída atómicamente:  
   consumir\_alerta\_maxima() → ZPOPMAX alertas:farmacovigilancia 1  
4. **Persistencia (MongoDB)**  
   Dictamen permanente en historial:  
   insert\_one en dictamenes\_alertas con resultado, investigador, acciones\_tomadas, fecha\_cierre.  
5. Si  
   1. **Sí, confirmado (Neo4j)**  
      Grafo actualizado con nueva evidencia o severidad revisada:  
      MERGE(pa1) \- \[i:INTERACTUA\_CON {tipo}\] \-\> (pa2) ON CREATE SET / ON MATCH SET  
   2. **Sí, falso positivo (Redis)**  
      Señal de farmacovigilancia corregida:  
      DECR contador:efectos:{med\_id} \+ max(0, valor) para evitar negativos  
      

El request body acepta un campo opcional nueva\_interaccion con pa1, pa2, tipo, severidad y mecanismo. Si resultado='confirmado' y este campo está presente, Neo4j ejecuta el MERGE con ON CREATE/ON MATCH para crear o actualizar la relación. Si resultado es 'falso\_positivo', Neo4j queda omitido y se registra el motivo en la respuesta.

**Atomicidad mediante Saga Orquestada (api/saga.py)**

OP-5 es la única operación del sistema que implementa el patrón Saga porque combina un paso destructivo (ZPOPMAX elimina la alerta de Redis permanentemente) con escrituras posteriores que pueden fallar. Sin mecanismo de compensación, un fallo de MongoDB dejaría la alerta consumida sin dictamen — pérdida irreversible.

La clase `SagaOrchestrator` registra un par acción/compensación por cada paso:

| Paso | Acción | Compensación si falla un paso posterior |
| ----- | ----- | ----- |
| 1a | ZPOPMAX — consume la alerta de mayor score | ZADD — re-inserta la alerta con su score original |
| 1b | DECR — decrementa el contador (falso positivo) | INCR — incrementa el contador de vuelta |
| 2 | insert\_one — persiste dictamen en MongoDB | delete\_one — borra el dictamen por \_id |
| 3 | MERGE — crea/actualiza relación en Neo4j | DELETE — borra la relación solo si fue creada nueva (ON CREATE) |

Si cualquier paso lanza excepción, `saga.compensate_all()` ejecuta las compensaciones en orden inverso (LIFO). El flag `_saga_created` guardado como propiedad de la relación Neo4j permite distinguir ON CREATE de ON MATCH: si la relación ya existía antes de esta operación, la compensación no la elimina para no destruir conocimiento preexistente.

# Coherencia entre Motores {#coherencia-entre-motores}

## El problema de la coherencia distribuida {#el-problema-de-la-coherencia-distribuida}

Un sistema con tres motores distintos no puede ofrecer transacciones ACID distribuidas sin un coordinador externo. Este sistema acepta esa limitación de forma explícita y adopta consistencia eventual con manejo de errores parciales.

## **6.2 Patrones implementados: best-effort (OP-1 a OP-4) y Saga Orquestada (OP-5)**

El sistema emplea dos estrategias de coherencia según la naturaleza de la operación.

**OP-1, 2, 3, 4 — Best-effort con registro de errores**

Las operaciones OP-1 a OP-4 son mayormente de lectura o tienen escrituras que no se encadenan (si una falla, la siguiente no depende de ella). Cada motor se accede en un bloque try/except independiente; los errores se acumulan sin detener el flujo:

| \# Patrón best-effort (OP-1 a OP-4) |
| :---- |
| errores \= {} |
|  |
| try: |
|     redis\_data \= operacion\_redis(r, params) |
| except Exception as e: |
|     errores\['redis'\] \= str(e) |
|  |
| try: |
|     mongo\_data \= operacion\_mongo(db, params) |
| except Exception as e: |
|     errores\['mongodb'\] \= str(e) |
|  |
| try: |
|     neo4j\_data \= operacion\_neo4j(driver, params) |
| except Exception as e: |
|     errores\['neo4j'\] \= str(e) |
|  |
| response \= {..., 'errores': errores if errores else None} |

**OP-5 — Saga Orquestada con transacciones compensatorias**

OP-5 requiere una estrategia más fuerte porque combina un paso destructivo irreversible (ZPOPMAX consume la alerta del sorted set) con escrituras posteriores en MongoDB y Neo4j. Sin compensación, un fallo de MongoDB dejaría la alerta perdida sin dictamen.

Se implementó el patrón **Saga Orquestada** (Richardson, 2018) en `api/saga.py`: un coordinador central ejecuta cada paso y registra su transacción compensatoria. Si cualquier paso falla, las compensaciones se ejecutan en orden inverso (LIFO):

| \# Patrón Saga Orquestada (OP-5) |
| :---- |
| saga \= SagaOrchestrator() |
|  |
| try: |
|     alerta \= consumir\_alerta\_maxima(r)          \# ZPOPMAX |
|     saga.register(\_compensar\_restaurar\_alerta, alerta)  \# → ZADD |
|  |
|     dictamen \= \_mongo\_persistir\_dictamen(req)    \# insert\_one |
|     saga.register(\_compensar\_borrar\_dictamen, dictamen) \# → delete\_one |
|  |
|     neo4j\_data \= \_neo4j\_crear\_interaccion(...)   \# MERGE |
|     saga.register(\_compensar\_borrar\_interaccion, ...) \# → DELETE si nueva |
|  |
|     return response\_ok |
|  |
| except Exception as exc: |
|     saga.compensate\_all()  \# revierte en orden inverso |
|     return response\_error |

 

## **6.3 Orden de escritura y justificación**

| Motor | Orden | Justificación |
| ----- | ----- | ----- |
| Redis | 1.° | Operación más crítica en tiempo real. Mayor impacto en la respuesta inmediata. Latencia submilisegundo. Si falla, el dato operativo se pierde pero no hay corrupción histórica. |
| MongoDB | 2.° | Persistencia permanente del evento. Si falla, el historial queda incompleto pero Redis ya tomó la acción inmediata. Reintentable en un proceso posterior. |
| Neo4j | 3.° | Actualización del grafo de conocimiento. Solo en OP-5 ante confirmación de nueva interacción. Es la escritura de menor urgencia y la más costosa de revertir. |

 

## **6.4 Garantías que ofrece el sistema y cuáles no**

| Garantía | ¿La ofrece? | Detalle |
| ----- | ----- | ----- |
| Atomicidad dentro de Redis | Sí | ZADD, INCR, LPUSH, ZPOPMAX son atómicos por diseño del motor. |
| Atomicidad entre motores | Parcial | OP-5 implementa Saga Orquestada: si un paso falla, las compensaciones revierten los pasos previos en orden inverso. OP-1 a OP-4 son best-effort sin compensación (sus escrituras no se encadenan). |
| Consistencia eventual | Sí | Los errores quedan registrados en el campo errores del response. Un proceso de reconciliación periódico puede comparar contadores Redis con reportes MongoDB. |
| Durabilidad en Redis | Parcial | Redis usa \--appendonly yes (AOF) en el docker-compose. Esto ofrece durabilidad ajustable con fsync each second por defecto. |
| Lectura siempre consistente | No | Un panel de OP-1 puede mostrar un contador Redis ya expirado mientras el reporte en MongoDB aún existe. Trade-off aceptable para el caso de uso. |
| Detección de inconsistencias | Sí | Cualquier fallo parcial queda expuesto en el campo errores del JSON de respuesta para auditoría posterior. |

# Comparación con Arquitectura Puramente Relacional {#comparación-con-arquitectura-puramente-relacional}

## Operación seleccionada: OP-2: Verificación de prescripción {#operación-seleccionada:-op-2:-verificación-de-prescripción}

Se elige OP-2 porque es la operación que mejor muestra el valor diferencial de la arquitectura políglota: detecta un riesgo clínico en tiempo real caminando traversal de Neo4j, velocidad de Redis y búsqueda histórica con aggregation de MongoDB. Resolver esta operación en SQL

## Solución SQL equivalente {#solución-sql-equivalente}

Resolver esta operación en SQL requiere replicar tres paradigmas distintos en un único modelo relacional. A continuación se muestra una versión simplificada, suponiendo las tablas: pacientes, medicamentos\_paciente, principios\_activos, interacciones\_pa, alertas, efectos\_adversos:

| \-- Paso 1: Neo4j equivalente (interacciones del paciente) |
| :---- |
| \-- O(n²) en SQL: producto cartesiano de PA del paciente |
| SELECT pa1.nombre, pa2.nombre, i.tipo, i.severidad, i.mecanismo |
| FROM medicamentos\_paciente mp1 |
| JOIN principios\_activos\_med pam1 ON mp1.med\_id \= pam1.med\_id |
| JOIN principios\_activos pa1 ON pam1.pa\_id \= pa1.id |
| JOIN medicamentos\_paciente mp2 ON mp2.paciente\_id \= mp1.paciente\_id |
| JOIN principios\_activos\_med pam2 ON mp2.med\_id \= pam2.med\_id |
| JOIN principios\_activos pa2 ON pam2.pa\_id \= pa2.id |
| JOIN interacciones\_pa i ON (i.pa1\_id \= pa1.id AND i.pa2\_id \= pa2.id) |
|                         OR (i.pa1\_id \= pa2.id AND i.pa2\_id \= pa1.id) |
| WHERE mp1.paciente\_id \= :pac\_id AND pa1.id \< pa2.id |
| ORDER BY CASE i.severidad WHEN 'contraindicada' THEN 1 ELSE 2 END; |
|  |
| \-- Paso 2: Redis equivalente (alertas activas sin TTL nativo) |
| SELECT \* FROM alertas |
| WHERE medicamento\_id \= :med\_id |
|   AND activa \= TRUE |
|   AND fecha\_expiracion \> NOW()  \-- requiere columna adicional |
| ORDER BY score DESC; |
|  |
| \-- Paso 3: MongoDB equivalente (historial de efectos adversos) |
| SELECT efecto, gravedad, pais\_reporte, fecha |
| FROM efectos\_adversos |
| WHERE medicamento\_id \= :med\_id |
|   AND fecha \>= NOW() \- INTERVAL '6 months' |
| ORDER BY fecha DESC LIMIT 10; |
|  |
| \-- Paso 4: Publicar alerta si hay riesgo |
| \-- No existe equivalente atómico a ZADD en SQL. |

## **7.3 Análisis comparativo** {#7.3-análisis-comparativo}

| Dimensión | SQL puro | Arquitectura poliglota |
| ----- | ----- | ----- |
| Detección de interacciones | JOIN O(n²) sobre todos los pares de medicamentos del paciente. Para 10 medicamentos: 45 pares posibles, cada uno requiere buscar en la tabla de interacciones. | Neo4j traversal O(grado del nodo): el motor recorre únicamente las aristas existentes del grafo. No genera pares que no tienen interacción. |
| Alertas activas | Tabla con campo fecha\_expiracion \+ consulta periódica para limpiar expiradas. Sin garantía de atomicidad en consumo concurrente. | Redis SORTED SET con EXPIRE implícito (TTL). ZPOPMAX atómico garantiza que dos médicos no consuman la misma alerta simultáneamente. |
| Historial con aggregation | GROUP BY estándar. Funciona bien hasta \~10M filas con índices correctos. | MongoDB aggregation pipeline con índice idx\_ea\_med\_gravedad\_fecha, optimizado para el patrón de acceso específico del dominio. |
| Publicar alerta si riesgo | Requiere lógica de aplicación \+ INSERT transaccional. Sin score compuesto nativo. | Redis ZADD con score flotante. Una sola llamada, atómica, O(log n). |
| Esquema de medicamentos | Tablas separadas por tipo (genérico, biológico, dispositivo) o columnas masivamente nulas. | MongoDB: atributos\_especificos como sub-objeto flexible. Sin columnas nulas, sin tablas de tipo. |
| Complejidad operacional | Un solo motor, un solo schema, un solo sistema de backup. Menor carga operacional. | Tres motores con ciclos de vida distintos. Mayor complejidad de despliegue, monitoreo y backup. |

## **7.4 Conclusión de la comparación** {#7.4-conclusión-de-la-comparación}

Para volúmenes pequeños y equipos con experiencia SQL, la arquitectura relacional es más simple de operar. La arquitectura poliglota es superior cuando (a) el grafo de interacciones crece en profundidad y los JOINs recursivos se vuelven prohibitivos, (b) la latencia de alertas operativas debe ser submilisegundo y SQL sobre disco no puede alcanzarla, y (c) los esquemas de medicamentos son heterogéneos y la normalización relacional produce columnas masivamente nulas. Los tres casos aplican al dominio farmacéutico de este sistema.

# Conclusiones {#conclusiones}

La incorporación de Redis completa una arquitectura que ahora cubre los tres tiempos del dato farmacéutico: el dato histórico y estructurado (MongoDB), el dato relacional de profundidad variable (Neo4j) y el dato operativo efímero en tiempo real (Redis). El resultado es un sistema políglota donde cada motor hace lo mejor sabe hacer.

## ¿Qué ganó el sistema? {#¿qué-ganó-el-sistema?}

* **Respuesta operativa en tiempo real:** las alertas de farmacovigilancia se publican y consumen con latencia submilisegundo. El sistema puede reaccionar a una ruptura de cadena de frío antes de que el lote afectado llegue al siguiente eslabón de distribución. Esto se puede ver con VEH002 en los datos de prueba.  
* **Control de acceso sin servidor de sesiones:** el TTL nativo de Redis implementa el vencimiento automático de permisos a ensayos clínicos según el rol.  
* **Cola de trabajo robusta y simple:** la lista FIFO garantiza que ningún reporte de efecto adverso se pierde y que se procesa en orden de llegada, con LPUSH/RPOP atómicos.  
* **Señal de farmacovigilancia automática:** el contador con EXPIRE de 86400 segundos implementa una ventana deslizante de 24 horas sin proceso de limpieza adicional, detectando automáticamente medicamentos con alta frecuencia de reportes adversos.

## ¿Qué complejidad adicional introdujo? {#¿qué-complejidad-adicional-introdujo?}

* **Tres sistemas que mantener:** backups, monitoreo, upgrades y troubleshooting se multiplication por tres.  
* **Curva de conocimiento:** el equipo debe dominar aggregation pipelines de MongoDB, Cypher de Neo4j y comandos Redis.  
* **Distinción de datos transitorio vs persistido:** la separación entre qué vive en Redis (temporal) y qué en MongoDB (permanente) debe estar documentada.

En síntesis, la arquitectura políglota es la decisión correcta para este dominio porque los problemas que resuelve son estructurales al problema farmacéutico y no pueden abordarse eficientemente con un único motor. La complejidad adicional que introduce es el precio por esas capacidades y la implementación realizada demuestra que ese costo es manejable.

# Bibliografía {#bibliografía}

## **Obligatoria — incorporada en esta entrega**

* **Redis Ltd. (s/f).** *Redis Documentation.* Recuperado de https://redis.io/docs/

* **Harrison, G. (2015).** *Next Generation Databases: NoSQL, NewSQL, and Big Data.* Apress. (Cap. 1 — Polyglot Persistence)

 

## **Complementaria**

* **Redis Ltd. (s/f).** *Redis Commands Reference.* Recuperado de https://redis.io/commands/

* **Pivert, O. (Ed.). (2018).** *NoSQL Data Models: Trends and Challenges.* ISTE. (Cap. 2\)

* **Richardson, C. (2018).** *Microservices Patterns.* Manning. (Cap. Saga, CQRS, Database per Service)

 

## **Documentación oficial — toda la entrega** {#documentación-oficial-—-toda-la-entrega}

* **MongoDB, Inc. (s/f).** *MongoDB Documentation.* Recuperado de https://www.mongodb.com/docs/

* **Neo4j, Inc. (s/f).** *Neo4j Documentation.* Recuperado de https://neo4j.com/docs/

* **Redis Ltd. (s/f).** *Redis Documentation.* Recuperado de https://redis.io/docs/

* **Tiangolo, S. (s/f).** *FastAPI Documentation.* Recuperado de https://fastapi.tiangolo.com/