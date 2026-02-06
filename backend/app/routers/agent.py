
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
    intent: str = None

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para interactuar con el agente 'Lúcio'.
    Versión Extendida: Soporta Crear, Editar y Borrar.
    """
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    # 1. Procesar con IA
    result = process_finance_message(db, current_user.id, user_msg)
    
    if result["status"] == "error":
        return ChatResponse(message=result["message"])
    
    data = result["data"]
    print(f"DEBUG [AGENT] AI JSON: {data}")
    intent = data.get("intent", "CREATE")
    
    # Clean names (strip brackets and arrows)
    if data.get("category"):
        data["category"] = data["category"].split("->")[-1].strip().strip("[]")
    if data.get("section"):
        data["section"] = data["section"].strip().strip("[]")
    if data.get("amount"):
        try:
            data["amount"] = int(str(data["amount"]).replace("$", "").replace(".", "").replace(",", ""))
        except: pass

    # --- PROCESAR INTENCIONES ---
    
    # A. BORRAR GASTO
    if intent == "DELETE":
        target_id = data.get("target_id")
        if not target_id:
            return ChatResponse(message="Entendí que quieres borrar algo, pero no logré identificar cuál gasto de la lista.", intent="DELETE")
        
        expense = db.query(Expense).filter(Expense.id == target_id, Expense.user_id == current_user.id).first()
        if not expense:
            return ChatResponse(message="No encontré ese gasto en mis registros.", intent="DELETE")

        # Sync a Sheets (Background)
        from app.services.sheets_service import delete_expense_from_sheet
        expense_info = {"date": str(expense.date), "concept": expense.concept, "amount": expense.amount}
        background_tasks.add_task(delete_expense_from_sheet, expense_info, current_user.tecnico_nombre)

        # Borrar en DB
        db.delete(expense)
        db.commit()
        return ChatResponse(message=data["response_text"], action_taken=True, intent="DELETE")

    # B. EDITAR GASTO
    elif intent == "UPDATE":
        # ... (previously updated logic remains similar but ensures intent is returned)
        target_id = data.get("target_id")
        if not target_id:
            return ChatResponse(message="¿Cuál gasto quieres editar? No logré identificarlo.", intent="UPDATE")
        
        expense = db.query(Expense).filter(Expense.id == target_id, Expense.user_id == current_user.id).first()
        if not expense:
            return ChatResponse(message="No encontré el gasto para editar.", intent="UPDATE")

        old_info = {"date": str(expense.date), "concept": expense.concept, "amount": expense.amount}

        updated = False
        if data.get("amount") is not None:
            expense.amount = int(data["amount"])
            updated = True
        if data.get("concept"):
            expense.concept = data["concept"]
            updated = True
        if data.get("category"):
            expense.category = data["category"]
            updated = True
        if data.get("section"):
            expense.section = data["section"]
            updated = True

        if updated:
            db.commit()
            db.refresh(expense)
        
        from app.services.sheets_service import update_expense_in_sheet
        new_info = {
            "date": str(expense.date), "concept": expense.concept, "category": expense.category,
            "section": expense.section or "OTROS", "amount": expense.amount, "payment_method": expense.payment_method
        }
        background_tasks.add_task(update_expense_in_sheet, old_info, new_info, current_user.tecnico_nombre)

        return ChatResponse(message=data["response_text"], action_taken=True, expense_data=new_info, intent="UPDATE")

    # C. CONSULTAR/CONVERSAR
    elif intent == "TALK":
        return ChatResponse(message=data["response_text"], action_taken=False, intent="TALK")

    # D. CREAR GASTO (Por defecto)
    else:
        try:
            from app.models.budget import Category
            exists = db.query(Category).filter(
                Category.user_id == current_user.id,
                Category.section == data["section"],
                Category.name == data["category"]
            ).first()

            if not exists:
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
            db.commit()
            db.refresh(new_expense)

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
            return ChatResponse(message="Entendí la intención, pero hubo un error técnico procesando el gasto.")
