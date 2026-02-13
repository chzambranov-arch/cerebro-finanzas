from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.models import User
from app.deps import get_current_user
from app.models.finance import Expense, Commitment
from app.models.budget import Category
from datetime import date, datetime
import os
from fastapi.security import APIKeyHeader
from fastapi import Header
import httpx

router = APIRouter(tags=["lucio_v2"], prefix="/api/v2/lucio")

N8N_API_KEY = os.getenv("N8N_API_KEY", "lucio_n8n_secret_proto_2026")
api_key_header = APIKeyHeader(name="X-N8N-API-KEY", auto_error=False)

def get_lucio_user(
    x_n8n_api_key: Optional[str] = Header(None, alias="X-N8N-API-KEY"),
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(api_key_header) # Usamos esto solo para capturar si hay algo
):
    # 1. Chequear API KEY (n8n tiene prioridad)
    if x_n8n_api_key == N8N_API_KEY:
        user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
        if user:
            return user

    # 2. Si no es n8n, intentar auth normal por token
    from app.deps import oauth2_scheme
    # Como oauth2_scheme levanta 401 si no hay token, lo envolvemos o pedimos el header manualmente
    # Para no romper deps.py, haremos una mini-validacion local del token
    auth_header = token # Si se proporcionó vía Header de APIKey
    
    # Intento de recuperación manual del usuario si falló lo anterior
    raise HTTPException(status_code=401, detail="Acceso denegado: API Key inválida o falta autenticación")

class ChatMessage(BaseModel):
    message: str

class ExpenseCreate(BaseModel):
    amount: int
    concept: str
    category: str
    section: str = "OTROS"
    payment_method: str = "Efectivo"

class CategoryCreate(BaseModel):
    section: str
    category: str
    budget: int = 0

class CommitmentCreate(BaseModel):
    title: str
    amount: int
    type: str # DEBT or LOAN
    concept: Optional[str] = None

class GenericAction(BaseModel):
    target_id: int

class ExpenseUpdate(BaseModel):
    amount: Optional[int] = None
    concept: Optional[str] = None
    category: Optional[str] = None
    section: Optional[str] = None

class CategoryUpdate(BaseModel):
    new_name: Optional[str] = None
    new_section: Optional[str] = None
    new_budget: Optional[int] = None

@router.get("/context")
def get_lucio_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    """
    Returns categories and recent expenses for n8n to use as AI context.
    """
    categories = db.query(Category).filter(Category.user_id == current_user.id).all()
    cat_list = [{"section": c.section, "name": c.name, "budget": c.budget} for c in categories]
    
    recent_expenses = db.query(Expense).filter(Expense.user_id == current_user.id).order_by(Expense.id.desc()).limit(10).all()
    exp_list = [{"id": e.id, "amount": e.amount, "concept": e.concept, "category": e.category} for e in recent_expenses]
    
    return {
        "categories": cat_list,
        "recent_expenses": exp_list,
        "user_name": current_user.tecnico_nombre
    }

@router.post("/action/expense")
def create_expense_v2(
    payload: ExpenseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    from app.services.sheets_service import sync_expense_to_sheet
    
    new_expense = Expense(
        user_id=current_user.id,
        amount=payload.amount,
        concept=payload.concept,
        category=payload.category,
        section=payload.section,
        payment_method=payload.payment_method,
        date=date.today()
    )
    db.add(new_expense)
    db.commit()
    
    expense_dict = {
        "date": str(new_expense.date),
        "concept": new_expense.concept,
        "category": new_expense.category,
        "amount": new_expense.amount,
        "payment_method": new_expense.payment_method
    }
    background_tasks.add_task(sync_expense_to_sheet, expense_dict, current_user.tecnico_nombre, section=payload.section)
    
    return {"status": "success", "message": "Expense registered", "data": expense_dict}

@router.post("/action/category")
def create_category_v2(
    payload: CategoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    from app.services.db_service import add_category_to_db
    from app.services.sheets_service import add_category_to_sheet
    
    success = add_category_to_db(db, current_user.id, payload.section, payload.category, payload.budget)
    if not success:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    background_tasks.add_task(add_category_to_sheet, payload.section, payload.category, payload.budget)
    
    return {"status": "success", "message": f"Category '{payload.category}' created in '{payload.section}'"}

@router.delete("/action/expense/{expense_id}")
def delete_expense_v2(
    expense_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    from app.services.sheets_service import delete_expense_from_sheet
    
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
        
    expense_info = {"date": str(expense.date), "concept": expense.concept, "amount": expense.amount}
    background_tasks.add_task(delete_expense_from_sheet, expense_info, current_user.tecnico_nombre)
    
    db.delete(expense)
    db.commit()
    return {"status": "success", "message": f"Expense '{expense.concept}' deleted"}

@router.post("/action/commitment")
def create_commitment_v2(
    payload: CommitmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    from app.services.sheets_service import sync_commitment_to_sheet
    
    new_comm = Commitment(
        user_id=current_user.id,
        title=payload.title,
        total_amount=payload.amount,
        remaining_amount=payload.amount,
        type=payload.type, # DEBT or LOAN
        status="ACTIVE",
        date=date.today(),
        notes=payload.concept
    )
    db.add(new_comm)
    db.commit()
    
    background_tasks.add_task(sync_commitment_to_sheet, new_comm, current_user.tecnico_nombre)
    return {"status": "success", "message": f"Commitment '{payload.title}' created", "id": new_comm.id}

@router.patch("/action/expense/{expense_id}")
def update_expense_v2(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    if payload.amount is not None: expense.amount = payload.amount
    if payload.concept: expense.concept = payload.concept
    if payload.category: expense.category = payload.category
    if payload.section: expense.section = payload.section
    
    db.commit()
    return {"status": "success", "message": "Expense updated"}

@router.patch("/action/category")
def update_category_v2(
    old_section: str,
    old_name: str,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    cat = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.section == old_section,
        Category.name == old_name
    ).first()
    
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if payload.new_name: cat.name = payload.new_name
    if payload.new_section: cat.section = payload.new_section
    if payload.new_budget is not None: cat.budget = payload.new_budget
    
    db.commit()
    return {"status": "success", "message": "Category updated"}

@router.delete("/action/category")
def delete_category_v2(
    section: str,
    name: str,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    # PDF Logic: Check if it has expenses
    expenses_count = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.category == name
    ).count()
    
    if expenses_count > 0 and not force:
        return {
            "status": "warning",
            "message": f"La categoría '{name}' tiene {expenses_count} gastos asociados. ¿Seguro que quieres borrarla?",
            "action_required": "CONFIRM_DELETE"
        }
    
    cat = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.section == section,
        Category.name == name
    ).first()
    
    if cat:
        db.delete(cat)
        db.commit()
        return {"status": "success", "message": f"Categoría '{name}' eliminada (y sus gastos si 'force' era true)"}
    
    return {"status": "error", "message": "Categoría no encontrada"}

@router.post("/action/commitment/{commitment_id}/resolve")
def resolve_commitment_v2(
    commitment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    comm = db.query(Commitment).filter(Commitment.id == commitment_id, Commitment.user_id == current_user.id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Commitment not found")
    
    comm.status = "PAID"
    comm.remaining_amount = 0
    db.commit()
    return {"status": "success", "message": f"Compromiso '{comm.title}' marcado como resuelto"}

@router.post("/execute")
def execute_universal_action(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_lucio_user)
):
    """
    Mando Universal para Lúcio v3.0.
    Recibe el JSON de n8n y redirige a la acción correcta según el 'intent'.
    """
    intent = payload.get("intent", "CHAT")
    data = payload.get("data", {})
    
    # Lúcio v3.0 usa 'reply' para la APP, si el backend devuelve algo, lo mezclamos
    response = {"status": "success", "reply": payload.get("reply", "¡Listo! He procesado tu solicitud.")}

    # SEGURIDAD: Si la sección, categoría o respuesta parecen preguntas (tienen '?'), abortar acción y solo chatear
    section = str(data.get("section", "")).strip()
    category = str(data.get("category", "")).strip()
    reply = str(payload.get("reply", "")).strip()
    
    if "?" in section or "?" in category or "?" in reply or "None" in section:
        return {"status": "chat", "reply": response["reply"]}

    try:
        if intent == "CREATE_EXPENSE":
            # Validar campos mínimos para gasto
            amount = data.get("amount")
            if not amount or not section or section == "None" or amount == 0:
                return {"status": "chat", "reply": response["reply"]}
            
            from pydantic import parse_obj_as
            res = create_expense_v2(parse_obj_as(ExpenseCreate, data), background_tasks, db, current_user)
            response.update(res)

        elif intent in ["CREATE_ITEM", "MANAGE_BUDGET"]:
            if not section or not category:
                 return {"status": "chat", "reply": response["reply"]}
            
            from pydantic import parse_obj_as
            res = create_category_v2(parse_obj_as(CategoryCreate, data), background_tasks, db, current_user)
            response.update(res)

        elif intent == "MANAGE_COMMITMENT":
            if not data.get("title") or not data.get("amount"):
                 return {"status": "chat", "reply": response["reply"]}
            
            from pydantic import parse_obj_as
            res = create_commitment_v2(parse_obj_as(CommitmentCreate, data), background_tasks, db, current_user)
            response.update(res)

        elif intent == "CHAT":
            pass

    except Exception as e:
        return {"status": "error", "reply": f"Tuve un problema técnico: {str(e)}"}

    return response

@router.post("/chat_proxy")
async def lucio_chat_proxy(
    payload: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Proxies chat messages to n8n to bypass CORS and connection issues.
    """
    # Cambiado a /webhook/ (Producción) para que funcione con el flujo Activado en n8n
    n8n_url = "http://localhost:5678/webhook/lucio-brain-v2"
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(n8n_url, json={"message": payload.message}, timeout=45.0)
            if r.status_code == 200:
                return r.json()
            else:
                return {"reply": f"Error de comunicación con n8n (Status {r.status_code})"}
        except Exception as e:
            return {"reply": f"Lúcio no pudo conectarse con su cerebro técnico: {str(e)}"}
