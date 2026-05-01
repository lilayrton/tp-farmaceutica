from pydantic import BaseModel, Field
from typing import Optional


class VerificarPrescripcionRequest(BaseModel):
    paciente_id: str = Field(..., examples=["PAC-2024-00001"])
    medicamento_id: str = Field(..., examples=["MED001"])


class NuevaInteraccion(BaseModel):
    pa1: str = Field(..., description="Nombre del primer principio activo")
    pa2: str = Field(..., description="Nombre del segundo principio activo")
    tipo: str = Field(..., examples=["farmacocinetica"])
    severidad: str = Field(..., examples=["grave"])
    mecanismo: str = Field(default="", description="Descripción del mecanismo")


class CerrarAlertaRequest(BaseModel):
    alerta_id: str = Field(..., examples=["ALT-A1B2C3D4"])
    medicamento_id: str = Field(..., examples=["MED001"])
    resultado: str = Field(..., examples=["confirmado", "falso_positivo"])
    investigador_id: str = Field(..., examples=["INV001"])
    acciones_tomadas: str = Field(default="", description="Acciones correctivas realizadas")
    nueva_interaccion: Optional[NuevaInteraccion] = Field(
        default=None,
        description="Si se confirma nueva interacción, se crea en Neo4j"
    )
