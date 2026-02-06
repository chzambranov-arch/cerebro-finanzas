
from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.models import User
from app.deps import get_current_user
from app.models.finance import Expense
from datetime import date
from app.services.ai_service import process_finance_message
from app.services.sheets_service import sync_expense_to_sheet, add_category_to_sheet
from app.services.db_service import add_category_to_db, get_dashboard_data_from_db

router = APIRouter(tags=["agent"])

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    action_taken: bool = False
    expense_data: dict = None

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para interactuar con el agente 'Lúcio'.
    Recibe texto, procesa con Gemini, crea el gasto y retorna respuesta.
    """
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    # 1. Procesar con IA
    result = process_finance_message(db, current_user.id, user_msg)
    
    if result["status"] == "error":
        return ChatResponse(message=result["message"])
    
    data = result["data"]
    
    # 2. Crear Gasto en BBDD
    try:
        # Verificar si la categoría existe, si no, crearla (Auto-learning básico)
        # Esto es un plus: el agente puede crear categorías si Gemini sugirió una nueva lógica
        from app.models.budget import Category
        exists = db.query(Category).filter(
            Category.user_id == current_user.id,
            Category.section == data["section"],
            Category.name == data["category"]
        ).first()

        if not exists:
            # Crear categoría nueva al vuelo
            print(f"[AGENT] Creating inferred category: {data['section']}/{data['category']}")
            add_category_to_db(db, current_user.id, data["section"], data["category"], 0)
            try:
                add_category_to_sheet(data["section"], data["category"], 0)
            except: pass

        new_expense = Expense(
            user_id=current_user.id,
            amount=int(data["amount"]),
            concept=data["concept"],
            category=data["category"],
            section=data["section"],
            payment_method=data["payment_method"],
            date=date.today(),
            image_url=None
        )
        db.add(new_expense)
        b = db.commit()
        db.refresh(new_expense)

        # 3. Sync a Sheets en Background
        expense_dict = {
            "date": str(new_expense.date),
            "concept": new_expense.concept,
            "category": new_expense.category,
            "amount": new_expense.amount,
            "payment_method": new_expense.payment_method,
            "image_url": None
        }
        background_tasks.add_task(sync_expense_to_sheet, expense_dict, current_user.tecnico_nombre, section=data["section"])

        return ChatResponse(
            message=data["response_text"], 
            action_taken=True,
            expense_data=expense_dict
        )

    except Exception as e:
        print(f"Error Agent Action: {e}")
        return ChatResponse(message="Entendí la intención, pero hubo un error técnico guardando el gasto.")
