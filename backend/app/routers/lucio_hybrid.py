"""
Router HÍBRIDO: IA + n8n
Este endpoint permite a n8n llamar al cerebro de la IA.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

from app.database import get_db
from app.models.user import User
from app.deps import get_current_user
from app.services import db_service

router = APIRouter(tags=["lucio_hybrid"], prefix="/api/v3/lucio")

# Configuración de seguridad para n8n (mismo token que n8n enviará)
N8N_API_KEY = os.getenv("N8N_WEBHOOK_TOKEN", "lucio_secret_token_2026_change_me")

def get_lucio_user_hybrid(
    authorization: Optional[str] = Header(None),
    x_n8n_api_key: Optional[str] = Header(None, alias="X-N8N-API-KEY"),
    db: Session = Depends(get_db)
):
    """
    Permite autenticar vía Bearer token (App) o API KEY (n8n/dev)
    """
    # 1. Si viene por API KEY de n8n
    if x_n8n_api_key == N8N_API_KEY:
        user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
        if not user: user = db.query(User).first()
        return user

    # 2. Si viene por Authorization header normal (App)
    if authorization:
        try:
            token_str = authorization.replace("Bearer ", "")
            return get_current_user(db=db, token=token_str)
        except:
            pass
            
    # 3. Fallback para desarrollo: Usar el primer usuario que exista
    user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
    if not user: user = db.query(User).first()
    return user

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    status: str
    reply: str
    action_taken: bool = False
    gasto_id: Optional[int] = None
    carpeta: Optional[Dict] = None
    item: Optional[Dict] = None
    alertas: Optional[List[Dict]] = None
    falta_crear: Optional[str] = None
    gastos: Optional[List[Dict]] = None

@router.post("/chat", response_model=ChatResponse)
async def chat_con_lucio_hybrid(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user_hybrid)
):
    """
    Endpoint principal para chat (n8n Orchestrator)
    
    Nueva arquitectura:
    1. Guarda mensaje del usuario
    2. Envía a n8n vía webhook
    3. n8n orquesta: Contexto + OpenAI + Ejecución
    4. Retorna respuesta de n8n al frontend
    """
    import httpx
    
    # Guardar mensaje en historial
    db_service.add_chat_msg(db, current_user.id, "user", request.message)
    
    # Preparar payload para n8n
    n8n_payload = {
        "message": request.message,
        "user_id": current_user.id
    }
    
    # Headers de autenticación
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json"
    }
    
    # URL del webhook de n8n
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/lucio-gastos")
    
    try:
        # Enviar a n8n (timeout 30s)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                n8n_webhook_url,
                json=n8n_payload,
                headers=headers
            )
            response.raise_for_status()
            
            # Obtener respuesta de n8n
            n8n_response = response.json()
            
            # Guardar respuesta del asistente
            reply_text = n8n_response.get("reply", "🤔")
            db_service.add_chat_msg(db, current_user.id, "assistant", reply_text)
            
            # Retornar tal cual lo que n8n envió
            return ChatResponse(**n8n_response)
            
    except httpx.TimeoutException:
        error_msg = "⏱️ n8n tardó demasiado en responder. Intenta de nuevo."
        db_service.add_chat_msg(db, current_user.id, "assistant", error_msg)
        return ChatResponse(
            status="error",
            reply=error_msg,
            action_taken=False
        )
    
    except httpx.HTTPStatusError as e:
        error_msg = f"❌ Error en n8n: {e.response.status_code}"
        db_service.add_chat_msg(db, current_user.id, "assistant", error_msg)
        return ChatResponse(
            status="error",
            reply=error_msg,
            action_taken=False
        )
    
    except Exception as e:
        error_msg = f"❌ Error conectando con n8n: {str(e)}"
        db_service.add_chat_msg(db, current_user.id, "assistant", error_msg)
        return ChatResponse(
            status="error",
            reply=error_msg,
            action_taken=False
        )

@router.get("/context")
def get_context_for_debug(db: Session = Depends(get_db), current_user: User = Depends(get_lucio_user_hybrid)):
    lucio = LucioAIHybrid(user_id=str(current_user.id), db=db)
    return {"user_id": current_user.id, "contexto": lucio._obtener_contexto()}
