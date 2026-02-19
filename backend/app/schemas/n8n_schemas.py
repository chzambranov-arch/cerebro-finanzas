"""
Schemas Pydantic para validación de requests/responses n8n
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal, Any
from datetime import datetime


# ============= REQUEST SCHEMAS =============

class GastoRequestN8N(BaseModel):
    """
    Schema para request desde App → n8n
    """
    user_id: str = Field(..., description="ID del usuario")
    fecha: Optional[str] = Field(None, description="Fecha del gasto (YYYY-MM-DD)")
    descripcion: str = Field(..., min_length=1, description="Descripción del gasto")
    monto: float = Field(..., gt=0, description="Monto del gasto")
    
    carpeta: Optional[str] = Field(None, description="Nombre de la carpeta")
    item: Optional[Any] = Field(None, description="Nombre o ID del item (null para esporádico)")
    
    tipo_gasto: Literal["FIJO", "CON_SALDO", "ESPORADICO"] = Field(..., description="Tipo de gasto")
    canal: str = Field(default="app", description="Canal de origen")
    
    # Contexto para inferencia (sin LLM pesado)
    contexto_5_lineas: Optional[List[str]] = Field(
        None, 
        max_items=5,
        description="Últimas 5 líneas de contexto del usuario"
    )
    
    @validator('fecha', pre=True, always=True)
    def set_fecha_default(cls, v):
        if v is None:
            return datetime.now().strftime("%Y-%m-%d")
        return v
    
    @validator('tipo_gasto')
    def validate_tipo_gasto(cls, v):
        if v not in ["FIJO", "CON_SALDO", "ESPORADICO"]:
            raise ValueError("tipo_gasto debe ser FIJO, CON_SALDO o ESPORADICO")
        return v
    
    @validator('item')
    def validate_item_esporadico(cls, v, values):
        # Si es ESPORADICO, item debe ser null
        if values.get('tipo_gasto') == 'ESPORADICO' and v is not None:
            raise ValueError("Item debe ser null para gastos esporádicos")
        return v


class CrearCarpetaRequest(BaseModel):
    """Request para crear carpeta"""
    user_id: str
    nombre_carpeta: str
    saldo_inicial: float = Field(0.0, ge=0)
    mes: Optional[str] = None


class CrearItemRequest(BaseModel):
    """Request para crear item"""
    user_id: str
    carpeta: str
    nombre_item: str
    tipo_item: Literal["FIJO", "CON_SALDO"]
    
    # Para CON_SALDO
    saldo_item: Optional[float] = Field(None, ge=0)
    
    # Para FIJO
    monto_fijo: Optional[float] = Field(None, ge=0)
    fecha_pago: Optional[str] = None  # Día del mes


# ============= RESPONSE SCHEMAS =============

class CarpetaInfo(BaseModel):
    """Info de carpeta en respuesta"""
    nombre: str
    gastado_total: float
    saldo_disponible: float
    saldo_inicial: float


class ItemInfo(BaseModel):
    """Info de item en respuesta"""
    nombre: str
    tipo_item: str
    gastado_item: float
    saldo_item: Optional[float] = None
    pagado_mes: Optional[str] = None


class AlertaInfo(BaseModel):
    """Info de alerta"""
    tipo: Literal["SALDO_BAJO", "SOBREPASO", "FIJO_DUPLICADO"]
    mensaje: str
    nivel: Literal["INFO", "WARNING", "ERROR"]


class GastoResponseN8N(BaseModel):
    """
    Response estándar desde n8n → App
    
    Estados posibles:
    - OK: Gasto registrado exitosamente
    - NEEDS_INFO: Falta información (crear carpeta/item)
    - NEEDS_CONFIRMATION: Requiere confirmación del usuario
    - ERROR: Error en el procesamiento
    """
    status: Literal["OK", "NEEDS_INFO", "NEEDS_CONFIRMATION", "ERROR"]
    mensaje: str
    
    # Datos del gasto registrado (si status=OK)
    gasto_id: Optional[int] = None
    carpeta: Optional[CarpetaInfo] = None
    item: Optional[ItemInfo] = None
    
    # Alertas generadas
    alertas: List[AlertaInfo] = []
    
    # Para NEEDS_INFO: qué falta crear
    falta_crear: Optional[Literal["carpeta", "item"]] = None
    
    # Para NEEDS_CONFIRMATION: acción requerida
    action: Optional[str] = None
    payload_reintento: Optional[dict] = None
    
    class Config:
        schema_extra = {
            "example_ok": {
                "status": "OK",
                "mensaje": "Gasto registrado exitosamente",
                "gasto_id": 123,
                "carpeta": {
                    "nombre": "Hogar",
                    "gastado_total": 125990,
                    "saldo_disponible": 174010,
                    "saldo_inicial": 300000
                },
                "item": {
                    "nombre": "Supermercado",
                    "tipo_item": "CON_SALDO",
                    "gastado_item": 100000,
                    "saldo_item": 100000
                },
                "alertas": []
            },
            "example_needs_info": {
                "status": "NEEDS_INFO",
                "mensaje": "La carpeta 'Hogar' no existe. Por favor créala primero.",
                "falta_crear": "carpeta",
                "alertas": []
            },
            "example_needs_confirmation": {
                "status": "NEEDS_CONFIRMATION",
                "mensaje": "Este gasto fijo ya está marcado como pagado este mes. ¿Quieres duplicarlo?",
                "action": "DUPLICAR_FIJO",
                "payload_reintento": {
                    "user_id": "u_123",
                    "descripcion": "Netflix",
                    "monto": 9990
                },
                "alertas": []
            }
        }


# ============= CONTEXTO SCHEMAS =============

class ContextoUpdate(BaseModel):
    """Update de contexto de usuario"""
    user_id: str
    lineas: List[str] = Field(..., max_items=5)
