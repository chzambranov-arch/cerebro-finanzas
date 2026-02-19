"""
DEPRECATED: La lógica de IA ahora vive en n8n (Arquitectura v4.0)

Este archivo se mantiene como referencia de la arquitectura v3.0, donde
FastAPI gestionaba OpenAI internamente.

NUEVA ARQUITECTURA (v4.0):
- FastAPI: Servicios de datos (API REST)
- n8n: Orquestador (OpenAI + Lógica de decisión)
- Flujo: App → FastAPI → n8n → [Contexto + OpenAI] → FastAPI → App

NO usar este archivo en código nuevo. Ver:
- app/routers/lucio_hybrid.py (Proxy a n8n)
- app/services/n8n_service.py (Ejecutor de acciones)
"""
import os
import json
import httpx
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
# from openai import OpenAI  # DEPRECATED: OpenAI ahora se llama desde n8n

from app.models.finance import Folder, Item
from app.schemas.n8n_schemas import GastoRequestN8N, GastoResponseN8N
from app.services.n8n_service import N8NService


class LucioAIHybrid:
    """
    Agente IA Híbrido:
    1. Interpreta lenguaje natural (Gemini/OpenAI)
    2. Infiere carpeta/item usando contexto
    3. Envía datos estructurados a n8n
    4. n8n persiste y actualiza saldos
    """
    
    def __init__(self, user_id: str, db: Session):
        self.user_id = user_id
        self.db = db
        
        # DEPRECATED: OpenAI ahora se invoca desde n8n
        # Configurar OpenAI Async
        # api_key = os.getenv("OPENAI_API_KEY")
        # if api_key:
        #     from openai import AsyncOpenAI
        #     self.client = AsyncOpenAI(api_key=api_key)
        #     self.model = "gpt-3.5-turbo" 
        # else:
        #     self.client = None
        self.client = None  # Placeholder para compatibilidad
    
    async def procesar_mensaje(
        self,
        mensaje: str,
        history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Punto de entrada principal
        
        Args:
            mensaje: Mensaje del usuario ("Sushi 15000")
            history: Historial de conversación
            
        Returns:
            Dict con status y datos
        """
        # 1. Obtener contexto del usuario (carpetas/items)
        contexto = self._obtener_contexto()
        
        # 2. Interpretar mensaje con IA
        interpretacion = await self._interpretar_con_ia(mensaje, contexto, history)
        
        # 3. Ejecutar acción según interpretación
        if interpretacion["intent"] == "CREATE_EXPENSE":
            return await self._registrar_gasto(interpretacion, mensaje)
        
        elif interpretacion["intent"] == "CREATE_FOLDER":
            return await self._crear_carpeta(interpretacion)
        
        elif interpretacion["intent"] == "CREATE_ITEM":
            return await self._crear_item(interpretacion)
        
        elif interpretacion["intent"] == "LIST_EXPENSES":
            return await self._listar_gastos(interpretacion)
        
        elif interpretacion["intent"] == "CHAT":
            return {
                "status": "chat",
                "reply": interpretacion.get("reply", "¿En qué puedo ayudarte?"),
                "action_taken": False
            }
        
        else:
            return {
                "status": "chat",
                "reply": "No entendí eso. ¿Puedes reformular?",
                "action_taken": False
            }
    
    def _obtener_contexto(self) -> Dict[str, Any]:
        """
        Obtiene carpetas e items del usuario para contexto IA
        """
        try:
            # Filter folders by user_id
            carpetas = self.db.query(Folder).filter(Folder.user_id == int(self.user_id)).all()
            
            contexto = {
                "carpetas": []
            }
            
            for carpeta in carpetas:
                # Use relationship to get items (and handle Enum serialization if needed)
                items_data = []
                for item in carpeta.items:
                    items_data.append({
                        "nombre": item.name,
                        "tipo": item.type.value if hasattr(item.type, "value") else str(item.type),
                        "saldo": item.budget
                    })
                
                contexto["carpetas"].append({
                    "nombre": carpeta.name,
                    "saldo": carpeta.initial_balance,
                    "items": items_data
                })
            
            return contexto
        except Exception as e:
            print(f"Error obteniendo contexto: {e}")
            return {"carpetas": []}
    
    async def _interpretar_con_ia(
        self,
        mensaje: str,
        contexto: Dict,
        history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Usa Gemini para interpretar el mensaje
        
        Returns:
            {
                "intent": "CREATE_EXPENSE",
                "data": {
                    "monto": 15000,
                    "descripcion": "Sushi",
                    "carpeta": "Ocio",
                    "item": "Restaurantes",
                    "tipo_gasto": "ESPORADICO"
                },
                "confidence": 0.95,
                "reply": "Registré $15.000 en Ocio > Restaurantes"
            }
        """
        if not self.client:
            return self._fallback_parsing(mensaje)

        # Prompt para OpenAI
        prompt = f"""Eres Lúcio, asistente financiero. Interpreta el mensaje del usuario y extrae:

CONTEXTO DEL USUARIO:
{json.dumps(contexto, indent=2, ensure_ascii=False)}

REGLAS:
- Si menciona un monto y descripción → intent: CREATE_EXPENSE
- Si dice "crear carpeta X" → intent: CREATE_FOLDER
- Si dice "crear item X en carpeta Y" → intent: CREATE_ITEM
- Si pregunta por gastos → intent: LIST_EXPENSES
- Si es conversación general → intent: CHAT

TIPOS DE GASTO:
- ESPORADICO: Gasto sin presupuesto específico (ej: "Café 2000")
- CON_SALDO: Item con presupuesto (ej: "Supermercado 25000")
- FIJO: Pago mensual fijo (ej: "Pagué Netflix")

INFERENCIA:
- Usa el contexto para inferir carpeta e item correcto
- Si no estás seguro, usa "Personal" como carpeta default
- Si el item no existe y es CON_SALDO/FIJO, marca needs_item_creation: true

MENSAJE DEL USUARIO:
"{mensaje}"

RESPONDE EN JSON (solo JSON, sin texto adicional):
{{
  "intent": "CREATE_EXPENSE|CREATE_FOLDER|CREATE_ITEM|LIST_EXPENSES|CHAT",
  "data": {{
    "monto": 15000,
    "descripcion": "Sushi",
    "carpeta": "Ocio",
    "item": "Restaurantes",
    "tipo_gasto": "ESPORADICO|CON_SALDO|FIJO"
  }},
  "needs_item_creation": false,
  "confidence": 0.95,
  "reply": "Mensaje natural de confirmación"
}}
"""

        try:
            # Call OpenAI Chat Completion (ASYNC)
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un asistente financiero útil que responde siempre en JSON estricto."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            text = completion.choices[0].message.content.strip()
            
            interpretacion = json.loads(text)
            return interpretacion
            
        except Exception as e:
            print(f"Error en IA (OpenAI): {e}")
            return self._fallback_parsing(mensaje)
    
    def _fallback_parsing(self, mensaje: str) -> Dict[str, Any]:
        """
        Parsing simple sin IA (fallback)
        """
        palabras = mensaje.split()
        
        # Buscar monto (número)
        monto = None
        for palabra in palabras:
            palabra_limpia = palabra.replace(".", "").replace(",", "")
            if palabra_limpia.isdigit():
                monto = int(palabra_limpia)
                break
        
        if monto:
            # Es un gasto
            descripcion = " ".join([p for p in palabras if not p.replace(".", "").replace(",", "").isdigit()])
            
            return {
                "intent": "CREATE_EXPENSE",
                "data": {
                    "monto": monto,
                    "descripcion": descripcion or "Gasto",
                    "carpeta": "Personal",  # Default
                    "item": None,
                    "tipo_gasto": "ESPORADICO"
                },
                "confidence": 0.6,
                "reply": f"Registré ${monto:,} como gasto esporádico"
            }
        
        # Si no hay monto, es chat
        return {
            "intent": "CHAT",
            "confidence": 0.5,
            "reply": "¿En qué puedo ayudarte? Puedes decirme algo como 'Almuerzo 5000'"
        }
    
    async def _registrar_gasto(
        self,
        interpretacion: Dict,
        mensaje_original: str
    ) -> Dict[str, Any]:
        """
        Registra el gasto usando n8n
        """
        data = interpretacion["data"]
        
        # Crear request para n8n
        gasto_request = GastoRequestN8N(
            user_id=self.user_id,
            descripcion=data.get("descripcion", mensaje_original),
            monto=data["monto"],
            carpeta=data.get("carpeta", "Personal"),
            item=data.get("item"),
            tipo_gasto=data.get("tipo_gasto", "ESPORADICO"),
            canal="app"
        )
        
        # Enviar a n8n
        resultado = await N8NService.registrar_gasto(gasto_request)
        
        # Formatear respuesta
        if resultado.status == "OK":
            reply = interpretacion.get("reply", f"✅ Registré ${data['monto']:,}")
            
            # Agregar info de saldos
            if resultado.carpeta:
                reply += f"\n\n💰 Saldo {resultado.carpeta.nombre}: ${resultado.carpeta.saldo_disponible:,}"
            
            # Agregar alertas
            if resultado.alertas:
                reply += "\n\n⚠️ Alertas:"
                for alerta in resultado.alertas:
                    reply += f"\n• {alerta.mensaje}"
            
            return {
                "status": "success",
                "reply": reply,
                "action_taken": True,
                "gasto_id": resultado.gasto_id,
                "carpeta": resultado.carpeta.dict() if resultado.carpeta else None,
                "item": resultado.item.dict() if resultado.item else None,
                "alertas": [a.dict() for a in resultado.alertas]
            }
        
        elif resultado.status == "NEEDS_INFO":
            # Falta crear carpeta o item
            return {
                "status": "needs_info",
                "reply": resultado.mensaje,
                "action_taken": False,
                "falta_crear": resultado.falta_crear
            }
        
        else:
            return {
                "status": "error",
                "reply": resultado.mensaje,
                "action_taken": False
            }
    
    async def _crear_carpeta(self, interpretacion: Dict) -> Dict[str, Any]:
        """Crea una carpeta"""
        data = interpretacion["data"]
        resultado = await N8NService.crear_carpeta(
            user_id=self.user_id,
            nombre_carpeta=data["nombre"],
            saldo_inicial=data.get("saldo_inicial", 0)
        )
        
        return {
            "status": "success" if resultado["status"] == "OK" else "error",
            "reply": resultado["mensaje"],
            "action_taken": resultado["status"] == "OK"
        }
    
    async def _crear_item(self, interpretacion: Dict) -> Dict[str, Any]:
        """Crea un item"""
        data = interpretacion["data"]
        resultado = await N8NService.crear_item(
            user_id=self.user_id,
            carpeta=data["carpeta"],
            nombre_item=data["nombre"],
            tipo_item=data.get("tipo", "CON_SALDO"),
            saldo_item=data.get("saldo")
        )
        
        return {
            "status": "success" if resultado["status"] == "OK" else "error",
            "reply": resultado["mensaje"],
            "action_taken": resultado["status"] == "OK"
        }
    
    async def _listar_gastos(self, interpretacion: Dict) -> Dict[str, Any]:
        """Lista gastos recientes"""
        from app.models.finance import Expense
        from sqlalchemy import desc
        
        # Query Expenses table (mapped to 'expenses')
        gastos = self.db.query(Expense).filter(
            Expense.user_id == int(self.user_id)
        ).order_by(desc(Expense.date)).limit(5).all()
        
        if not gastos:
            return {
                "status": "chat",
                "reply": "No tienes gastos registrados aún.",
                "action_taken": False
            }
        
        reply = "📋 Últimos gastos:\n\n"
        decoded_gastos = []
        
        for g in gastos:
            # Expense model: amount, description, folder (obj), etc.
            folder_name = g.folder.name if g.folder else "Sin carpeta"
            reply += f"• {g.description}: ${g.amount:,} ({folder_name})\n"
            
            decoded_gastos.append({
                "id": g.id,
                "descripcion": g.description,
                "monto": g.amount,
                "carpeta": folder_name,
                "fecha": g.date.isoformat() if g.date else None
            })
        
        return {
            "status": "chat",
            "reply": reply,
            "action_taken": False,
            "gastos": decoded_gastos
        }
