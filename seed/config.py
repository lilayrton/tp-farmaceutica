"""
Configuración central del generador de datos de prueba.
Todos los parámetros de volumen, conexión y semillas están aquí.
"""

from dataclasses import dataclass

# ── Semilla aleatoria — misma semilla = mismos datos siempre ─────────────────
RANDOM_SEED = 42

# ── Volúmenes requeridos por el enunciado ────────────────────────────────────
CANT_PRINCIPIOS_ACTIVOS  = 80
CANT_MEDICAMENTOS        = 200
CANT_DISTRIBUIDORES      = 50
CANT_LOTES               = 150
CANT_ENSAYOS             = 20
CANT_EFECTOS_ADVERSOS    = 300
CANT_PACIENTES_NEO4J     = 50   # solo en Neo4j

# ── Parámetros de negocio ────────────────────────────────────────────────────
MAX_ESLABONES_LOTE       = 8
MIN_ESLABONES_LOTE       = 3
MAX_PA_POR_MEDICAMENTO   = 4
MIN_PA_POR_MEDICAMENTO   = 1
MAX_CENTROS_POR_ENSAYO   = 8
MIN_CENTROS_POR_ENSAYO   = 2

# Garantías para que las consultas (a)(d)(e) del TP tengan resultados
MEDS_CON_SEÑAL_FARMACOVIG = 6   # medicamentos que superarán el umbral de consulta (e)
EFECTOS_POR_MED_SEÑAL     = 5   # reportes graves en último semestre por medicamento señal
PACIENTES_CON_INTERACCION = 10  # pacientes neo4j con combinaciones peligrosas (consulta a)
PA_CONTRAINDICADOS_MIN    = 20  # pares INTERACTUA_CON severidad grave/contraindicada

# ── Conexiones (ajustar a tu entorno) ────────────────────────────────────────
import os
MONGO_URI  = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB   = os.getenv("MONGO_DB", "farmaceutica_tp")

NEO4J_URI  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "farmaceutica")

# ── Países del sistema ───────────────────────────────────────────────────────
PAISES = ["AR", "BR", "UY", "CL", "MX", "CO", "PE", "PY", "BO", "EC"]

# ── Terminología MedDRA simplificada ────────────────────────────────────────
TERMINOS_MEDDRA = [
    "Náuseas", "Vómitos", "Cefalea", "Mareos", "Erupciones cutáneas",
    "Prurito", "Urticaria", "Diarrea", "Constipación", "Dolor abdominal",
    "Fatiga", "Insomnio", "Palpitaciones", "Hipotensión", "Bradicardia",
    "Taquicardia", "Elevación de transaminasas", "Insuficiencia renal aguda",
    "Anafilaxia", "Angioedema", "Trombocitopenia", "Leucopenia",
    "Hiperglucemia", "Hipoglucemia", "Convulsiones", "Alucinaciones",
]

# ── Categorías terapéuticas ──────────────────────────────────────────────────
CATEGORIAS_TERAPEUTICAS = {
    "betalactamico":    ["antibiotico", "antiinfeccioso"],
    "quinolona":        ["antibiotico", "antiinfeccioso"],
    "macrolido":        ["antibiotico", "antiinfeccioso"],
    "IECA":             ["antihipertensivo", "cardiovascular"],
    "ARA2":             ["antihipertensivo", "cardiovascular"],
    "estatina":         ["hipolipemiante", "cardiovascular"],
    "bifosfonato":      ["oseo", "metabolismo"],
    "ISRS":             ["antidepresivo", "psiquiatrico"],
    "IRSN":             ["antidepresivo", "psiquiatrico"],
    "antipsicótico":    ["psiquiatrico"],
    "biguanida":        ["antidiabetico", "metabolismo"],
    "sulfonilurea":     ["antidiabetico", "metabolismo"],
    "opioide":          ["analgesico", "dolor"],
    "AINE":             ["analgesico", "antiinflamatorio"],
    "corticoide":       ["antiinflamatorio", "inmunologia"],
    "inmunosupresor":   ["inmunologia"],
    "anticoagulante":   ["hematologia", "cardiovascular"],
    "antiagregante":    ["hematologia", "cardiovascular"],
    "broncodilatador":  ["respiratorio"],
    "corticoide_inh":   ["respiratorio", "antiinflamatorio"],
}
