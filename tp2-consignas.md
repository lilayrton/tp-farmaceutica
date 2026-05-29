# INGENIERÍA DE DATOS II

## TRABAJO PRÁCTICO INTEGRADOR - 2.ª ENTREGA (TEMA 13)
**Empresa Farmacéutica — Medicamentos y Ensayos Clínicos**
**Motores:** 1.a Entrega MongoDB $\cdot$ Neo4j | Motor adicional Redis
**Capa:** Poliglota MongoDB + Neo4j + Redis
**Unidades evaluadas V:** Acceso desde aplicaciones · Persistencia Poliglota
**Fecha de entrega:** Lunes 1 de junio de 2026
**Modalidad Grupal (5 integrantes)** — Extensión de la 1.a Entrega

**Defensa oral**: Luego de corregidas ambas entregas (fecha a confirmar)

---

## 1. Introducción
Este documento extiende la 1.a Entrega.
Esta segunda entrega no reemplaza el trabajo ya entregado en la primera instancia, sino que lo extiende. El grupo debe presentar este documento junto con el código adicional que implementa el tercer motor y la capa de persistencia poliglota. Todo lo desarrollado en la 1.a Entrega sigue vigente y forma parte del sistema completo que se defenderá oralmente.

La primera entrega estableció el núcleo: el catálogo de medicamentos, trazabilidad de lotes y ensayos clínicos en MongoDB, y la red de interacciones entre principios activos en Neo4j. Esta segunda entrega incorpora dos nuevos desafíos:

*   **Tercer motor — Redis:** Incorporación de Redis para gestionar las alertas de farmacovigilancia en tiempo real, el control de acceso a datos de ensayos clínicos, la cola de procesamiento de reportes de efectos adversos y el monitoreo de temperatura de la cadena de frío.
*   **Capa de persistencia poliglota:** Implementación de una aplicación con interfaz mínima que integra los tres motores en operaciones de negocio cohesivas, decidiendo conscientemente qué datos consulta en cada motor y cómo ensambla la respuesta.

Cada decisión de diseño debe estar justificada en el informe escrito.

## 2. Tercer Motor: Redis
### 2.1 Justificación de incorporación
El dominio farmacéutico tiene tres naturalezas de datos claramente diferenciadas:

*   **Datos históricos y estructurados:** El catálogo de medicamentos, los lotes de producción, los ensayos clínicos y los efectos adversos viven en MongoDB con esquema altamente variable por tipo de medicamento.
*   **Datos relacionales y de red:** La red de interacciones entre principios activos y la detección de combinaciones peligrosas viven en Neo4j.
*   **Datos operativos en tiempo real:** Las alertas activas de farmacovigilancia (que requieren respuesta en horas), el monitoreo de temperatura de la cadena de frío (cada vehículo refrigerado reporta cada 5 minutos), la cola de reportes de efectos adversos pendientes de evaluación médica y el control de acceso a datos clínicos confidenciales son datos operativos y temporales que Redis gestiona de forma óptima.

Redis resuelve estos casos con **SORTED SETs** para alertas ordenadas por severidad, **STREAMS** para el monitoreo de temperatura, **LISTs** para la cola de evaluación de reportes y **TTL** para el control de acceso temporal.

> **⚠️ Error conceptual frecuente — Redis no es una base de datos secundaria**
Redis no debe usarse como un simple caché de lo que ya está en MongoDB. En este sistema, Redis es la fuente de verdad para los datos operativos en tiempo real. MongoDB almacena el historial de lo que ya ocurrió. Redis gestiona lo que está ocurriendo ahora.

### 2.2 Modelado en Redis — Estructuras de datos
El grupo debe modelar en Redis las estructuras para la operación de farmacovigilancia en tiempo real:

| Estructura Redis | Caso de uso en el dominio | Justificación técnica |
| :--- | :--- | :--- |
| **SORTED SET** | Cola de alertas de farmacovigilancia | El equipo médico siempre atiende las alertas activas ordenadas por severidad (score = nivel de riesgo $\times$ urgencia) usando ZPOPMAX para consumo atómico. |
| **STREAM** | Log de lecturas de temperatura de la cadena de frío | Registro inmutable y ordenado de `cadena_frío:vehicle_id` con ventana temporal, permitiendo detectar rupturas o inconsistencias de *timestamp*. |
| **LIST** | Cola de reportes de efectos adversos | LPUSH al recibir el reporte. RPOP cuando el médico toma el siguiente caso (FIFO por fecha de reporte). |
| **HASH** | Estado de acceso a un ensayo clínico | Control de acceso temporal a `investigador_id` basado en rol, institución y permisos. TTL automático revoca el acceso. |
| **STRING (contador)** | Contador de reportes de efectos adversos por medicamento en las 24h | INCR atómico con EXPIRE automático para ventanas temporales deslizantes. |

**Convención de nombres de clave (key naming)**
La convención es: `entidad:identificador:atributo`.

**Ejemplos:**
*   `alertas:farmacovigilancia`: $\to$ **SORTED SET** con alertas activas ordenadas por severidad.
*   `temperatura:stream`: $\to$ **STREAM** de lecturas de temperatura de la cadena de frío.
*   `cola:efectos_adversos`: $\to$ **LIST** con reportes pendientes de evaluación médica.
*   `acceso:ensayo:ENS001:INV00789`: $\to$ **HASH** con permisos de acceso del investigador al ensayo.
*   `contador:efectos:MED00456`: $\to$ **STRING** contador de reportes del medicamento en 24h.

El contador con `EXPIRE` es un patrón Redis para ventanas temporales deslizantes sin proceso de limpieza manual.

## 3. Requerimientos de Implementación — Redis
El grupo deberá implementar y documentar las siguientes operaciones en Redis:

### 3.1 Sistema de alertas de farmacovigilancia
1.  Implementar la cola de alertas de farmacovigilancia usando **SORTED SETs** con score compuesto.
2.  Implementar las siguientes operaciones:
    a) Publicar una alerta con nivel de severidad (1–5) y tipo (`interaccion_grave`/`reaccion_adversa`/`lote_comprometido`).
    b) El equipo médico consume la alerta de mayor severidad (**ZPOPMAX**).
    c) Consultar todas las alertas activas por tipo de alerta.
    d) Escalar una alerta existente aumentando su score si se confirma el riesgo.
    e) Justificar en el informe por qué un **SORTED SET** es preferible a una **LIST** para este caso.

### 3.2 Monitoreo de cadena de frío
3.  Implementar el monitoreo de temperatura de la cadena de frío usando **STREAM Redis**.
4.  Implementar las siguientes operaciones:
    a) Registrar una lectura de temperatura: `vehiculo_id`, `temperatura_celsius`, `timestamp`, `latitud`, `longitud`.
    b) Detectar ruptura de cadena de frío: temperatura fuera de rango en dos lecturas consecutivas del mismo vehículo.
    c) Consultar las últimas 12 lecturas de un vehículo para análisis de tendencia.
    d) Al detectar ruptura, publicar automáticamente una alerta en el **SORTED SET** de farmacovigilancia.
    e) Justificar en el informe por qué un **STREAM** es más adecuado que un **SORTED SET** para el log de temperatura.

### 3.3 Control de acceso a ensayos clínicos y cola de evaluación
5.  Implementar el control de acceso temporal a datos de ensayos clínicos y la cola de evaluación de reportes de efectos adversos.
6.  Implementar las siguientes operaciones:
    a) Otorgar acceso a un ensayo clínico con TTL según el rol (investigador: 8h, auditor: 4h, regulador: 24h).
    b) Verificar si un investigador tiene acceso vigente antes de mostrar datos del ensayo.
    c) Encolar un reporte de efecto adverso recibido (**LPUSH**).
    d) El médico evaluador toma el próximo reporte pendiente (**RPOP**).
    e) Incrementar el contador de reportes del medicamento en las últimas 24h y alertar si supera el umbral (**INCR + EXPIRE**).

## 4. Capa de Persistencia Poliglota
### ¿Qué es la persistencia poliglota?
La persistencia poliglota es una decisión arquitectural: distintos motores de base de datos gestionan distintas partes del dominio según sus fortalezas. No es simplemente 'usar tres bases de datos'. Implica diseñar explícitamente qué datos viven en cada motor, cómo fluyen entre ellos, cómo se mantiene la coherencia y qué motor responde cada tipo de consulta. (Harrison, 2015, Cap. 1; Pivert, 2018, Cap. 2)

### 4.1 Responsabilidades por motor
El grupo debe documentar explícitamente qué responsabilidad tiene cada motor en el sistema:

| Motor | Responsabilidad | Datos que gestiona |
| :--- | :--- | :--- |
| **MongoDB** | Fuente de verdad histórica | Catálogo de medicamentos, lotes, ensayos clínicos, reportes históricos de efectos adversos persistidos. |
| **Neo4j** | Red de relaciones | Red de interacciones entre principios activos, detección de grafos combinaciones peligrosas. |
| **Redis** | Estado operativo en tiempo real | Alertas de farmacovigilancia en tiempo real, monitoreo de cadena de frío, cola de evaluación, control de acceso. |

**Atención — coherencia entre motores**
Cuando ocurre un evento de negocio relevante, deben actualizarse los motores que correspondan. El grupo debe documentar en el informe cómo gestiona esta coherencia y qué sucede si una de las escrituras falla (estrategia de manejo de errores parciales).

*Ejemplo:* Cuando se recibe un reporte de efecto adverso grave:
*   **Redis:** Encola el reporte para evaluación (**LIST**); publica alerta en el **SORTED SET** de farmacovigilancia; incrementa el contador del medicamento.
*   **Neo4j:** Consulta el grafo de interacciones para identificar si hay combinaciones de medicamentos que pueden explicar el efecto.
*   **MongoDB:** Persiste el reporte con todos sus atributos para el registro histórico de farmacovigilancia.

### 4.2 Operaciones poliglotas requeridas
La aplicación debe implementar exactamente 5 operaciones que integren múltiples motores. Las operaciones marcadas con (*) deben usar los tres motores simultáneamente en una sola respuesta.

| Operación | MongoDB | Neo4j | Redis |
| :--- | :--- | :--- | :--- |
| **OP-1 Panel de farmacovigilancia en tiempo real (\*)** | Medicamentos con más reportes de efectos adversos en el último mes. | Principios activos con mayor número de interacciones graves conocidas. | Alertas activas ordenadas por severidad, reportes pendientes de evaluación, medicamentos con contador elevado en 24h. |
| **OP-2 Verificación de prescripción y detección de riesgos (\*)** | Historial de efectos adversos del paciente con medicamentos similares. | Interacciones con los medicamentos actuales del paciente. | Alertas activas sobre el medicamento a prescribir; si hay alerta grave, escalar la severidad en SORTED SET. |
| **OP-3 Trazabilidad de lote y alerta de ruptura de cadena de frío (2 motores)** | Trazabilidad completa del lote: desde producción hasta distribuidores actuales. | — Detecta la ruptura en el STREAM de temperatura; publica alerta en el SORTED SET; registra el evento. | *Note: The table in the source material seems to imply Redis/MongoDB for this one, but the text below clarifies the focus.* |
| **OP-4 Análisis de interacciones para un nuevo medicamento (2 motores)** | Datos del medicamento en desarrollo y sus principios activos. | Para cada principio activo, recorre el grafo de interacciones y lista todas las combinaciones conocidas con medicamentos existentes, ordenadas por severidad. | — |
| **OP-5 Cierre de alerta de farmacovigilancia (\*)** | Persiste el dictamen: confirmado/descartado, acciones tomadas, investigador responsable. | Si la alerta confirma una nueva interacción, agrega o actualiza la relación en el grafo. | Elimina la alerta del SORTED SET (ZPOPMAX ya la consumió); decrementa el contador del medicamento si es falso positivo. |

A continuación, se detalla el comportamiento esperado de cada operación:

**OP-1 Panel de farmacovigilancia en tiempo real (\*) — 3 motores**
El equipo de farmacovigilancia ve el estado de riesgo del sistema:
*   **Redis:** Top 5 alertas activas por severidad (ZREVRANGE); tamaño de la cola de evaluación (LLEN); medicamentos con contador > umbral en las últimas 24h.
*   **MongoDB:** Medicamentos con mayor cantidad de reportes de efectos adversos en el último mes.
*   **Neo4j:** Principios activos con mayor número de interacciones graves o contraindicadas en el grafo.

El informe debe documentar el ensamblado del panel y el tiempo de respuesta esperado.

**OP-2 Verificación de prescripción y detección de riesgos (\*) — 3 motores**
Cuando se va a prescribir un medicamento, el sistema verifica riesgos en tiempo real:
*   **Neo4j:** Dado el medicamento y los que ya toma el paciente, detectar interacciones en el grafo.
*   **Redis:** Verificar si hay alertas activas sobre ese medicamento en el SORTED SET.
*   **MongoDB:** Recuperar el historial de efectos adversos del paciente con medicamentos del mismo grupo.
*   Si se detecta interacción grave, **publicar alerta en el SORTED SET** con alta severidad.

El informe debe documentar el orden de consultas y qué acción se toma si los tres motores detectan riesgo simultáneamente.

**OP-3 Trazabilidad de lote y alerta de ruptura de cadena de frío — 2 motores**
Cuando se detecta ruptura de cadena de frío en un lote, el sistema actúa:
*   **Redis:** Lee las últimas lecturas del vehículo del **STREAM**; detecta la ruptura de cadena de frío; publica alerta de severidad máxima en el **SORTED SET**.
*   **MongoDB:** Recupera la trazabilidad completa del lote: cuántas unidades, en qué distribuidores y farmacias están actualmente.

El informe debe justificar por qué Neo4j no participa en esta operación.

**OP-4 Análisis de interacciones para un nuevo medicamento — 2 motores**
Antes de aprobar un nuevo medicamento, el sistema mapea todas sus interacciones potenciales:
*   **MongoDB:** Recupera los principios activos del medicamento en desarrollo.
*   **Neo4j:** Para cada principio activo, recorre el grafo de interacciones y lista todas las combinaciones conocidas con medicamentos existentes, ordenadas por severidad.

El informe debe justificar por qué Redis no participa en esta operación.

**OP-5 Cierre de alerta de farmacovigilancia (\*) — 3 motores**
El médico evaluador resuelve una alerta y el sistema actualiza los tres motores:
*   **Redis:** La alerta fue consumida con ZPOPMAX al iniciar la evaluación. Si el resultado es 'falso positivo', DECR del contador del medicamento.
*   **MongoDB:** Persiste el dictamen completo con la resolución y las acciones tomadas.
*   **Neo4j:** Si se confirma una nueva interacción, crea o actualiza la relación entre los principios activos involucrados.

El informe debe documentar el flujo completo desde la generación de la alerta hasta su resolución, indicando el estado de cada motor en cada etapa.

## 5. Interfaz de la Aplicación
La capa poliglota debe implementarse como una aplicación con interfaz mínima que permita ejecutar las 5 operaciones sin necesidad de modificar el código fuente. El grupo puede elegir entre:
*   **CLI (Command Line Interface):** La aplicación acepta comandos y argumentos por línea de comandos.
*   **API REST:** La aplicación expone endpoints HTTP invocables desde un cliente o navegador.
*   **Menú interactivo:** La aplicación presenta un menú numerado en la consola para seleccionar la operación y cargar parámetros.

**Requisitos mínimos de la interfaz**
Independientemente de la modalidad elegida, la interfaz debe cumplir:
1.  Las 5 operaciones poliglotas deben ser invocables sin modificar el código.
2.  Las conexiones a los tres motores deben configurarse mediante variables de entorno o archivo de configuración (no hardcodeadas).
3.  Los errores de conexión o de datos deben devolver mensajes descriptivos, no *stack traces* crudos.
4.  El README del repositorio debe incluir instrucciones claras para ejecutar la aplicación.

Justificar en el informe la modalidad elegida y por qué es adecuada para el caso de uso.

## 6. Informe Escrito — Estructura Obligatoria
El informe de esta segunda entrega es un documento adicional al de la primera entrega. Debe cubrir únicamente los contenidos nuevos:
7.  **Introducción:** Qué agrega esta entrega al sistema de la primera entrega y cómo se articula con lo ya entregado.
8.  **Justificación de Redis:** Por qué Redis para este dominio, qué problema resuelve que MongoDB y Neo4j no pueden resolver, qué alternativas se descartaron.
9.  **Modelado en Redis:** Estructuras de datos elegidas por caso de uso, convención de nombres de clave, justificación de cada decisión.
10. **Diseño de la capa poliglota:** Tabla de responsabilidades por motor, diagrama de flujo de datos para cada operación, decisiones de coherencia.
11. **Operaciones poliglotas:** Para cada una de las 5 operaciones: flujo de consultas, orden de motores, ensamblado de respuesta y estrategia ante fallos.
12. **Coherencia entre motores:** Qué sucede ante un fallo parcial en una escritura multi-motor. ¿Qué garantías ofrece el sistema y cuáles no?
13. **Comparación con arquitectura puramente relacional:** Elegir una de las 5 operaciones y mostrar cómo se resolvería en SQL puro. Analizar diferencias en complejidad, rendimiento y mantenibilidad.
14. **Conclusiones:** Reflexión crítica sobre la arquitectura poliglota: qué ganó el sistema con este diseño y qué complejidad adicional introdujo.
15. **Bibliografía:** Incorporar la documentación oficial de Redis y la bibliografía complementaria