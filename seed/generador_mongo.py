"""
Generador de documentos para las 6 colecciones MongoDB.
Schemas exactamente según documento v4 del TP.
"""

import random
from datetime import datetime, timedelta
from bson import ObjectId
from faker import Faker
from config import *
from datos_maestros import PRINCIPIOS_ACTIVOS_MAESTROS

fake = Faker("es_AR")
fake.seed_instance(RANDOM_SEED)
random.seed(RANDOM_SEED)

HOY = datetime.now()


def fecha_pasada(dias_min=30, dias_max=1800):
    return HOY - timedelta(days=random.randint(dias_min, dias_max))


def fecha_futura(dias_min=90, dias_max=1095):
    return HOY + timedelta(days=random.randint(dias_min, dias_max))


def fecha_reciente_semestre():
    return HOY - timedelta(days=random.randint(1, 180))


def fecha_reciente_anio():
    return HOY - timedelta(days=random.randint(1, 365))


# ── principios_activos ────────────────────────────────────────────────────────

def generar_principios_activos(maestros: list) -> tuple:
    docs   = []
    id_map = {}  # neo4j_node_id -> ObjectId

    familias_extra = list(CATEGORIAS_TERAPEUTICAS.keys())

    for pa_base in maestros:
        oid = ObjectId()
        doc = {
            "_id":             oid,
            "nombre":          pa_base["nombre"],
            "familia_quimica": pa_base["familia"],
            "mecanismo_accion":pa_base["mecanismo"],
            "vida_media":      pa_base["vida_media_horas"],
            "metabolismo": {
                "via_principal":               pa_base["via_metabolismo"],
                "enzimas":                     pa_base["enzimas"],
                "porcentaje_eliminacion_renal": 80 if pa_base["via_metabolismo"] == "renal" else 20,
            },
            "neo4j_node_id":   pa_base["neo4j_node_id"],
        }
        docs.append(doc)
        id_map[pa_base["neo4j_node_id"]] = oid

    n_extras = max(0, CANT_PRINCIPIOS_ACTIVOS - len(maestros))
    for i in range(n_extras):
        familia  = random.choice(familias_extra)
        nombre   = f"Compuesto-{fake.last_name()}-{random.randint(100, 999)}"
        neo4j_id = f"pa_{nombre.lower().replace(' ', '_').replace('-', '_')}"
        oid      = ObjectId()
        via      = random.choice(["renal", "hepatica", "mixta"])
        doc = {
            "_id":             oid,
            "nombre":          nombre,
            "familia_quimica": familia,
            "mecanismo_accion":f"Mecanismo de acción de {nombre}.",
            "vida_media":      round(random.uniform(1.0, 48.0), 1),
            "metabolismo": {
                "via_principal":               via,
                "enzimas":                     random.sample(["CYP3A4","CYP2D6","CYP2C9","CYP2C19"], k=random.randint(0, 2)),
                "porcentaje_eliminacion_renal": random.randint(10, 90),
            },
            "neo4j_node_id":   neo4j_id,
        }
        docs.append(doc)
        id_map[neo4j_id] = oid

    return docs, id_map


# ── medicamentos ──────────────────────────────────────────────────────────────

def generar_medicamentos(pa_docs: list, pa_id_map: dict) -> tuple:
    docs   = []
    id_map = {}

    formas      = ["capsula", "comprimido", "jarabe", "inyectable", "crema", "parche", "inhalador"]
    vias        = ["oral", "parenteral", "topica", "inhalatoria", "sublingual"]
    condiciones = ["libre", "bajo_receta", "receta_archivada"]
    estados     = ["activo"] * 9 + ["discontinuado"] + ["en_revision"]
    nombres_usados = set()

    for i in range(CANT_MEDICAMENTOS):
        if 30 <= i < 80:
            tipo = "biologico"
        elif 80 <= i < 100:
            tipo = "dispositivo_medico"
        else:
            tipo = "generico"

        n_pa = random.randint(MIN_PA_POR_MEDICAMENTO, MAX_PA_POR_MEDICAMENTO)
        pas_sel = random.sample(pa_docs, k=min(n_pa, len(pa_docs)))

        pa_embebidos = []
        for idx, pa in enumerate(pas_sel):
            pa_embebidos.append({
                "pa_id": pa["_id"],
                "nombre": pa["nombre"],
                "dosis_en_formulacion": f"{random.choice([100,200,250,500,750,1000])}mg",
                "rol": "activo" if idx == 0 else random.choice(["activo", "excipiente_clave"]),
            })

        nombre_comercial = f"{fake.last_name()} {random.choice([100,200,250,400,500,750,1000])}"
        while nombre_comercial in nombres_usados:
            nombre_comercial = f"{fake.last_name()} {random.choice([100,200,250,400,500,750,1000])}"
        nombres_usados.add(nombre_comercial)

        oid = ObjectId()

        if tipo == "biologico":
            atributos = {
                "origen":                    random.choice(["recombinante", "monoclonal", "derivado_plasma"]),
                "cadena_fria":               True,
                "temperatura_almacenamiento":"2-8°C",
            }
        elif tipo == "dispositivo_medico":
            atributos = {
                "clase_riesgo":  random.choice(["I", "II", "III"]),
                "vida_util_usos":random.randint(1, 100),
                "esteril":       random.choice([True, False]),
            }
        else:
            atributos = {
                "bioequivalencia_certificada": True,
                "marca_referencia": f"Marca-{fake.last_name()}",
            }

        doc = {
            "_id":               oid,
            "codigo":            f"MED{str(i+1).zfill(3)}",
            "nombre_comercial":  nombre_comercial,
            "nombre_generico":   pas_sel[0]["nombre"] if pas_sel else "Genérico",
            "forma_farmaceutica":random.choice(formas),
            "dosis":             pa_embebidos[0]["dosis_en_formulacion"] if pa_embebidos else "500mg",
            "via_administracion":random.choice(vias),
            "condicion_venta":   random.choice(condiciones),
            "pais_registro":     random.sample(PAISES, k=random.randint(1, 5)),
            "tipo":              tipo,
            "principios_activos":pa_embebidos,
            "atributos_especificos": atributos,
            "estado":            random.choice(estados),
        }
        docs.append(doc)
        id_map[nombre_comercial] = oid

    return docs, id_map


# ── distribuidores ────────────────────────────────────────────────────────────

def generar_distribuidores() -> tuple:
    docs   = []
    id_map = {}
    tipos_forzados = (
        ["mayorista"] * 10 + ["minorista"] * 15 +
        ["hospital"] * 12 + ["farmacia"] * 13
    )

    for i in range(CANT_DISTRIBUIDORES):
        tipo = tipos_forzados[i] if i < len(tipos_forzados) else random.choice(["mayorista","minorista","hospital","farmacia"])
        pais = random.choice(PAISES)
        razon_social = f"{fake.company()}"
        oid  = ObjectId()
        doc  = {
            "_id":         oid,
            "razon_social":razon_social,
            "tipo":        tipo,
            "cuit":        f"{random.randint(20,34)}-{random.randint(10000000,99999999)}-{random.randint(0,9)}",
            "ubicacion": {
                "direccion":fake.address().replace("\n", ", "),
                "ciudad":   fake.city(),
                "pais":     pais,
            },
            "lotes_activos": [],
            "contacto": {
                "email":   fake.email(),
                "telefono":fake.phone_number(),
            },
            "habilitacion_anmat": f"HAB-{pais}-{random.randint(2010,2023)}-{random.randint(100,9999)}",
        }
        docs.append(doc)
        id_map[razon_social] = oid
    return docs, id_map


# ── lotes ─────────────────────────────────────────────────────────────────────

def generar_lotes(med_docs: list, dist_docs: list) -> list:
    """
    Genera lotes con cadena de distribución embebida (schema del documento v4).
    Garantía: 20 lotes vencen en < 90 días con stock activo (consulta b).
    """
    docs = []
    dist_por_tipo = {}
    for d in dist_docs:
        dist_por_tipo.setdefault(d["tipo"], []).append(d)

    lotes_proximos = 0

    for i in range(CANT_LOTES):
        med = random.choice(med_docs)
        cantidad_producida = random.randint(5000, 100000)

        if lotes_proximos < 20:
            vencimiento  = HOY + timedelta(days=random.randint(10, 89))
            estado_stock = random.choice(["en_distribucion", "en_planta"])
            lotes_proximos += 1
        else:
            vencimiento  = fecha_futura(dias_min=91, dias_max=730)
            estado_stock = random.choice(["en_distribucion", "en_planta", "agotado"])

        n_eslabones  = random.randint(MIN_ESLABONES_LOTE, MAX_ESLABONES_LOTE)
        cadena       = []
        fecha_actual = fecha_pasada(180, 600)

        for paso in range(1, n_eslabones + 1):
            if paso == 1:
                etapa          = "planta"
                entidad_nombre = f"Planta {fake.city()}"
                entidad_oid    = ObjectId()
            elif paso == n_eslabones:
                etapa          = random.choice(["farmacia", "hospital"])
                candidatos     = dist_por_tipo.get(etapa, dist_docs)
                dist           = random.choice(candidatos) if candidatos else None
                entidad_nombre = dist["razon_social"] if dist else f"{etapa.title()} {fake.city()}"
                entidad_oid    = dist["_id"]          if dist else ObjectId()
            else:
                etapa          = random.choice(["mayorista", "minorista"])
                candidatos     = dist_por_tipo.get(etapa, dist_docs)
                dist           = random.choice(candidatos) if candidatos else None
                entidad_nombre = dist["razon_social"] if dist else f"{etapa.title()} {fake.city()}"
                entidad_oid    = dist["_id"]          if dist else ObjectId()

            eslabon = {
                "paso":          paso,
                "etapa":         etapa,
                "entidad_id":    entidad_oid,
                "entidad_nombre":entidad_nombre,
                "fecha":         fecha_actual,
            }
            cadena.append(eslabon)
            fecha_actual = fecha_actual + timedelta(days=random.randint(3, 20))

        oid = ObjectId()
        doc = {
            "_id":               oid,
            "numero_lote":       f"LOT-{HOY.year}-{str(i+1).zfill(5)}",
            "medicamento_id":    med["_id"],
            "medicamento_nombre":med["nombre_comercial"],
            "planta_produccion": f"Planta {fake.city()}",
            "cantidad_producida":cantidad_producida,
            "fecha_fabricacion": fecha_pasada(200, 400),
            "fecha_vencimiento": vencimiento,
            "estado_stock":      estado_stock,
            "cadena_distribucion":cadena,
        }
        docs.append(doc)

        # Registrar en distribuidor (último eslabón no-planta)
        ultimo = cadena[-1]
        for dist in dist_docs:
            if dist["_id"] == ultimo.get("entidad_id"):
                dist["lotes_activos"].append({
                    "lote_id":           oid,
                    "numero_lote":       doc["numero_lote"],
                    "medicamento_nombre":doc["medicamento_nombre"],
                    "cantidad_actual":   random.randint(100, 5000),
                    "fecha_recepcion":   ultimo["fecha"],
                })
                break

    return docs


# ── ensayos_clinicos ──────────────────────────────────────────────────────────

def generar_ensayos(med_docs: list, pa_id_map: dict) -> list:
    """
    Garantía: al menos 5 en fase III y estado activo (consulta d).
    """
    docs  = []
    fases = ["I", "II", "III", "IV"]
    estados = ["activo", "suspendido", "completado", "cancelado"]
    paises_ensayo = ["AR", "BR", "UY", "CL", "MX", "CO"]
    pa_node_ids = list(pa_id_map.keys())

    for i in range(CANT_ENSAYOS):
        med = random.choice(med_docs)

        if i < 5:
            fase   = "III"
            estado = "activo"
        else:
            fase   = random.choice(fases)
            estado = random.choice(estados)

        n_centros = random.randint(MIN_CENTROS_POR_ENSAYO, MAX_CENTROS_POR_ENSAYO)
        centros   = []
        total_pac = 0
        for _ in range(n_centros):
            pac = random.randint(20, 300)
            total_pac += pac
            centros.append({
                "nombre":               f"Hospital {fake.last_name()} de {fake.city()}",
                "pais":                 random.choice(paises_ensayo),
                "ciudad":               fake.city(),
                "investigador_principal":f"Dr. {fake.first_name()} {fake.last_name()}",
                "pacientes_enrolados":  pac,
                "estado_centro":        random.choice(["activo", "completado"]),
            })

        inicio = fecha_pasada(180, 730)
        doc = {
            "_id":               ObjectId(),
            "nombre":            f"{med['nombre_generico'].split()[0][:6].upper()}-{fase}-{HOY.year}-{random.choice(paises_ensayo)}",
            "codigo_protocolo":  f"ECA-{HOY.year}-{str(i+1).zfill(3)}",
            "fase":              fase,
            "estado":            estado,
            "hipotesis":         f"El medicamento {med['nombre_comercial']} es no-inferior al tratamiento estándar en fase {fase}.",
            "medicamento_id":    med["_id"],
            "fecha_inicio":      inicio,
            "fecha_fin_estimada":inicio + timedelta(days=random.randint(365, 1095)),
            "centros_participantes":     centros,
            "total_pacientes_enrolados": total_pac,
            "resultados_preliminares":   f"Datos preliminares con resultados {random.choice(['prometedores','consistentes','mixtos'])}.",
        }
        docs.append(doc)
    return docs


# ── efectos_adversos ──────────────────────────────────────────────────────────

def generar_efectos_adversos(med_docs: list, lote_docs: list, pa_docs: list) -> list:
    """
    Schema según documento v4: usa campo `fecha` (no fecha_reporte).
    Paciente como sub-objeto {id_anonimo, edad, genero}.
    Garantía: 6 medicamentos superan umbral de señal (consulta e).
    """
    docs = []
    gravedades = ["leve", "moderada", "grave", "fatal"]

    meds_señal = random.sample(med_docs, min(MEDS_CON_SEÑAL_FARMACOVIG, len(med_docs)))
    contador = 0

    # Reportes graves recientes para medicamentos señal
    for med_señal in meds_señal:
        lotes_med = [l for l in lote_docs if l["medicamento_id"] == med_señal["_id"]] or [random.choice(lote_docs)]
        for _ in range(EFECTOS_POR_MED_SEÑAL):
            lote  = random.choice(lotes_med)
            pa_imp = random.choice(med_señal["principios_activos"])
            docs.append(_crear_efecto_adverso(
                med=med_señal, lote=lote,
                pa_nombre=pa_imp["nombre"], pa_oid=pa_imp["pa_id"],
                gravedad="grave",
                fecha=fecha_reciente_semestre(),
                todos_meds=med_docs,
            ))
            contador += 1

    # Resto hasta CANT_EFECTOS_ADVERSOS
    while contador < CANT_EFECTOS_ADVERSOS:
        med   = random.choice(med_docs)
        lotes = [l for l in lote_docs if l["medicamento_id"] == med["_id"]] or lote_docs
        lote  = random.choice(lotes)
        pa_imp = random.choice(med["principios_activos"]) if med["principios_activos"] else None
        docs.append(_crear_efecto_adverso(
            med=med, lote=lote,
            pa_nombre=pa_imp["nombre"] if pa_imp else "Desconocido",
            pa_oid=pa_imp["pa_id"]     if pa_imp else ObjectId(),
            gravedad=random.choices(gravedades, weights=[40, 35, 20, 5])[0],
            fecha=fecha_reciente_anio(),
            todos_meds=med_docs,
        ))
        contador += 1

    return docs


def _crear_efecto_adverso(med, lote, pa_nombre, pa_oid, gravedad, fecha, todos_meds):
    return {
        "_id":            ObjectId(),
        "medicamento_id": med["_id"],
        "medicamento_nombre": med["nombre_comercial"],
        "lote_id":        lote["_id"],
        "lote_numero":    lote["numero_lote"],
        "pa_implicados":  [{"pa_id": pa_oid, "nombre": pa_nombre}],
        "paciente": {
            "id_anonimo": f"PAC-{HOY.year}-{random.randint(10000, 99999)}",
            "edad":       random.randint(18, 85),
            "genero":     random.choice(["M", "F", "NB", "NE"]),
        },
        "descripcion":   f"Paciente presentó {random.choice(TERMINOS_MEDDRA).lower()} a las {random.randint(1,48)} horas.",
        "gravedad":       gravedad,
        "fecha":          fecha,
        "pais_reporte":   random.choice(PAISES),
        "combinacion_medicamentos": [random.choice(todos_meds)["_id"]] if random.random() > 0.5 else [],
    }
