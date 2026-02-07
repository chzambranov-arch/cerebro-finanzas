
from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.models import User
from app.deps import get_current_user
from app.models.finance import Expense, Commitment, PendingExpense, PushSubscription
from datetime import date, datetime
from app.services.ai_service import process_finance_message
from app.services.sheets_service import sync_expense_to_sheet, add_category_to_sheet, sync_commitment_to_sheet, delete_commitment_from_sheet, update_category_in_sheet, delete_category_from_sheet
from app.services.db_service import add_category_to_db, get_dashboard_data_from_db, update_category_in_db, delete_category_from_db
from app.models.budget import Category, Budget

router = APIRouter(tags=["agent"])

class ChatRequest(BaseModel):
    message: str
    pending_id: Optional[int] = None

class ChatResponse(BaseModel):
    message: str
    action_taken: bool = False
    expense_data: Optional[dict] = None
    intent: Optional[str] = None
    pending_id: Optional[int] = None

class PushSubKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubRequest(BaseModel):
    endpoint: str
    keys: PushSubKeys

@router.post("/push-subscribe")
def subscribe_push(
    payload: PushSubRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Guarda una suscripción de Push Notifications para el usuario actual.
    """
    # Verificar si ya existe el endpoint
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    
    if existing:
        existing.user_id = current_user.id 
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth
        )
        db.add(new_sub)
    
    db.commit()
    return {"message": "Suscripción guardada correctamente"}

@router.get("/check-pending", response_model=ChatResponse)
def check_pending_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verifica si hay gastos pendientes de categorización (desde correos).
    """
    pending = db.query(PendingExpense).filter(
        PendingExpense.user_id == current_user.id,
        PendingExpense.status == "PENDING"
    ).order_by(PendingExpense.created_at.asc()).first()

    if not pending:
        return ChatResponse(message="No hay gastos pendientes.")

    msg = f"¡Hola! Detecté un nuevo gasto de **${pending.amount:,}** en **{pending.concept}**. ¿A qué sub-categoría corresponde? 🔎"
    
    return ChatResponse(
        message=msg,
        action_taken=False,
        intent="ASK_CATEGORY",
        pending_id=pending.id
    )

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint para interactuar con el agente 'Lúcio'.
    """
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    # Si viene de un gasto pendiente
    pending_ref = None
    if request.pending_id:
        pending_ref = db.query(PendingExpense).filter(
            PendingExpense.id == request.pending_id,
            PendingExpense.user_id == current_user.id
        ).first()

    # 1. Guardar mensaje del usuario y recuperar historial
    from app.models.models import ChatHistory
    db.add(ChatHistory(user_id=current_user.id, role="user", message=user_msg))
    db.commit()

    history_objs = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).order_by(ChatHistory.id.desc()).limit(10).all()
    chat_history = [{"role": h.role, "content": h.message} for h in reversed(history_objs)]

    # 2. Procesar con IA
    pending_context = None
    if pending_ref:
        pending_context = f"El usuario está categorizando un gasto detectado: {pending_ref.concept} por ${pending_ref.amount}."
    
    result = process_finance_message(db, current_user.id, user_msg, extra_context=pending_context, history=chat_history)
    
    if result["status"] == "error":
        return ChatResponse(message=result["message"])
    
    # 2. Procesar Acciones (Soporte para múltiples acciones)
    data_items = result.get("data")
    if data_items is None:
         data_items = []
    elif isinstance(data_items, dict):
        data_items = [data_items]
    
    aggregated_responses = []
    final_action_taken = False
    last_expense_data = None
    
    for data in data_items:
        intent = data.get("intent", "CREATE")
        
        # Clean names
        if data.get("category"):
            data["category"] = data["category"].split("->")[-1].strip().strip("[]")
        if data.get("section"):
            data["section"] = data["section"].strip().strip("[]")
        
        if pending_ref and data.get("category") and data.get("section"):
            data["amount"] = pending_ref.amount
            data["concept"] = f"{pending_ref.concept} (Email)"
            pending_ref.status = "PROCESSED"
            db.commit()

        if data.get("amount"):
            try:
                data["amount"] = int(str(data["amount"]).replace("$", "").replace(".", "").replace(",", ""))
            except: pass

        response_text = data.get("response_text", "")

        # --- PROCESAR INTENCIONES ---
        
        # A. BORRAR GASTO
        if intent == "DELETE":
            target_id = data.get("target_id")
            if target_id:
                expense = db.query(Expense).filter(Expense.id == target_id, Expense.user_id == current_user.id).first()
                if expense:
                    from app.services.sheets_service import delete_expense_from_sheet
                    expense_info = {"date": str(expense.date), "concept": expense.concept, "amount": expense.amount}
                    background_tasks.add_task(delete_expense_from_sheet, expense_info, current_user.tecnico_nombre)
                    db.delete(expense)
                    db.commit()
                    final_action_taken = True
                    aggregated_responses.append(response_text or "Gasto eliminado.")
                else:
                    aggregated_responses.append("No encontré el gasto para borrar.")
            else:
                aggregated_responses.append("No identifique qué borrar.")

        # B. EDITAR GASTO
        elif intent == "UPDATE":
            target_id = data.get("target_id")
            if target_id:
                expense = db.query(Expense).filter(Expense.id == target_id, Expense.user_id == current_user.id).first()
                if expense:
                    old_info = {"date": str(expense.date), "concept": expense.concept, "amount": expense.amount}
                    if data.get("amount") is not None: expense.amount = int(data["amount"])
                    if data.get("concept"): expense.concept = data["concept"]
                    if data.get("category"): expense.category = data["category"]
                    if data.get("section"): expense.section = data["section"]
                    db.commit()
                    
                    from app.services.sheets_service import update_expense_in_sheet
                    new_info = {
                        "date": str(expense.date), "concept": expense.concept, "category": expense.category,
                        "section": expense.section or "OTROS", "amount": expense.amount, "payment_method": expense.payment_method
                    }
                    background_tasks.add_task(update_expense_in_sheet, old_info, new_info, current_user.tecnico_nombre)
                    final_action_taken = True
                    last_expense_data = new_info
                    aggregated_responses.append(response_text or "Gasto actualizado.")
                else:
                    aggregated_responses.append("No encontré el gasto para editar.")

        # C. CONSULTAR/CONVERSAR
        elif intent == "TALK":
             aggregated_responses.append(response_text)

        # ZZ. IGNORAR PENDIENTE
        elif intent == "IGNORE_PENDING":
            if pending_ref:
                pending_ref.status = "IGNORED"
                db.commit()
                final_action_taken = True
                aggregated_responses.append("Gasto ignorado.")

        # D. CREAR COMPROMISO
        elif intent == "CREATE_COMMITMENT":
            try:
                c_date = datetime.utcnow()
                raw_date = data.get("date")
                if raw_date:
                    try:
                        c_date = datetime.strptime(raw_date, "%Y-%m-%d")
                    except ValueError: pass

                new_comm = Commitment(
                    user_id=current_user.id,
                    title=data.get("concept") or data.get("category") or "Compromiso",
                    type=data.get("commitment_type", "DEBT"), 
                    total_amount=int(data.get("amount", 0)),
                    paid_amount=0,
                    status="PENDING",
                    created_at=c_date
                )
                db.add(new_comm)
                db.commit()
                background_tasks.add_task(sync_commitment_to_sheet, new_comm, current_user.tecnico_nombre)
                final_action_taken = True
                
                date_str = c_date.strftime("%d/%m")
                aggregated_responses.append(response_text or f"Compromiso creado ({date_str}).")
            except Exception as e:
                aggregated_responses.append(f"Error creando compromiso: {e}")

        # E. BORRAR COMPROMISO
        elif intent == "DELETE_COMMITMENT":
            target_id = data.get("target_id")
            if target_id:
                comm = db.query(Commitment).filter(Commitment.id == target_id, Commitment.user_id == current_user.id).first()
                if comm:
                    comm_id = comm.id
                    db.delete(comm)
                    db.commit()
                    background_tasks.add_task(delete_commitment_from_sheet, comm_id)
                    final_action_taken = True
                    aggregated_responses.append(response_text or "Compromiso eliminado.")
            else:
                 aggregated_responses.append("No identifiqué compromiso para borrar.")

        # F. MARCAR COMPROMISO COMO PAGADO
        elif intent == "MARK_PAID_COMMITMENT":
            raw_id = data.get("target_id")
            if raw_id:
                comm = db.query(Commitment).filter(Commitment.id == int(raw_id), Commitment.user_id == current_user.id).first()
                if comm:
                    comm.status = "PAID"
                    comm.paid_amount = comm.total_amount
                    db.commit()
                    background_tasks.add_task(sync_commitment_to_sheet, comm, current_user.tecnico_nombre)
                    final_action_taken = True
                    aggregated_responses.append(response_text or "Compromiso marcado pagado.")

        # H. ELIMINAR CATEGORIA O SECCIÓN
        elif intent == "DELETE_CATEGORY":
            target_type = data.get("target_type", "CATEGORY")
            sec = data.get("section")
            cat = data.get("category")
            target_name = cat if cat else sec

            if target_type == "SECTION" and (sec or cat):
                folder_to_delete = sec if sec else cat
                section_items = db.query(Category).filter(
                    Category.user_id == current_user.id,
                    Category.section.ilike(folder_to_delete)
                ).all()

                if section_items:
                    has_exp = db.query(Expense).filter(
                        Expense.user_id == current_user.id,
                        Expense.section.ilike(folder_to_delete)
                    ).first()

                    if has_exp:
                        aggregated_responses.append(f"No puedo eliminar la carpeta '{folder_to_delete}' porque tiene gastos registrados dentro.")
                    else:
                        for item in section_items: db.delete(item)
                        db.commit()
                        final_action_taken = True
                        aggregated_responses.append(f"Carpeta '{folder_to_delete}' eliminada.")
                else:
                    aggregated_responses.append(f"No encontré la carpeta '{folder_to_delete}'.")
            else:
                found_cat = None
                if sec and cat:
                     found_cat = db.query(Category).filter(
                         Category.user_id == current_user.id, 
                         Category.section.ilike(sec), 
                         Category.name.ilike(cat)
                     ).first()

                if not found_cat and cat:
                    found_cat = db.query(Category).filter(
                        Category.user_id == current_user.id, 
                        Category.name.ilike(cat)
                    ).first()

                if found_cat:
                    expenses_count = db.query(Expense).filter(
                        Expense.user_id == current_user.id,
                        Expense.section == found_cat.section,
                        Expense.category == found_cat.name
                    ).count()

                    if expenses_count > 0:
                        aggregated_responses.append(f"❌ No puedo eliminar '{found_cat.name}' porque tiene {expenses_count} gastos.")
                    else:
                        cat_name = found_cat.name
                        cat_sec = found_cat.section
                        db.delete(found_cat)
                        db.commit()
                        final_action_taken = True
                        aggregated_responses.append(f"Sub-categoría '{cat_name}' eliminada de la carpeta '{cat_sec}'.")
                else:
                    aggregated_responses.append(f"No encontré el ítem '{target_name}' para eliminar.")

        # I. EDITAR CATEGORIA (Renombrar, Mover o Cambiar Presupuesto)
        elif intent == "UPDATE_CATEGORY":
            sec = data.get("section")
            cat = data.get("category")
            new_name = data.get("new_name") or data.get("concept")
            
            raw_amount = data.get("amount")
            new_budget = None
            if raw_amount is not None:
                try:
                    val = int(raw_amount)
                    if val > 0: new_budget = val
                except: pass

            new_section = data.get("new_section")
            target_type = data.get("target_type", "CATEGORY")
            
            if target_type == "SECTION":
                if sec and new_name:
                     if update_category_in_db(db, current_user.id, section=sec, new_name=new_name, target_type="SECTION"):
                          aggregated_responses.append(response_text or f"Carpeta '{sec}' renombrada a '{new_name}'.")
                     else:
                          aggregated_responses.append(f"No pude renombrar la carpeta '{sec}'.")
            elif cat:
                found_cat = None
                if sec:
                     found_cat = db.query(Category).filter(
                        Category.user_id == current_user.id, 
                        Category.name == cat,
                        Category.section == sec
                     ).first()
                if not found_cat:
                    matches = db.query(Category).filter(
                        Category.user_id == current_user.id, 
                        Category.name == cat
                    ).all()
                    if len(matches) > 1:
                        sects = ", ".join([f"'{m.section}'" for m in matches])
                        aggregated_responses.append(f"El ítem '{cat}' existe en múltiples carpetas: {sects}. ¿A cuál te refieres?")
                        continue 
                    elif len(matches) == 1: found_cat = matches[0]
                
                if found_cat:
                    sec = found_cat.section
                    if update_category_in_db(db, current_user.id, sec, cat, new_name=new_name, new_budget=new_budget, new_section=new_section):
                        final_name = new_name if new_name else cat
                        final_section = new_section if new_section else sec
                        c_obj = db.query(Category).filter(Category.user_id==current_user.id, Category.section==final_section, Category.name==final_name).first()
                        current_budget = c_obj.budget if c_obj else 0
                        if not new_section: background_tasks.add_task(update_category_in_sheet, sec, cat, current_budget, new_cat=new_name)
                        final_action_taken = True
                        msg_parts = []
                        if new_name: msg_parts.append(f"renombrada a '{new_name}'")
                        if new_section: msg_parts.append(f"movida a carpeta '{new_section}'")
                        if new_budget is not None: msg_parts.append(f"presupuesto actualizado a ${new_budget:,}")
                        aggregated_responses.append(response_text or f"Subcategoría '{cat}' {' y '.join(msg_parts)}.")
                    else: aggregated_responses.append(f"No pude editar la subcategoría '{cat}'.")
                else: aggregated_responses.append(f"No encontré la subcategoría '{cat}'.")
            else: aggregated_responses.append("No entendí que categoría editar.")

        # G. CREAR CATEGORIA
        elif intent == "CREATE_CATEGORY":
            if data.get("section") and data.get("category"):
                exists = db.query(Category).filter(
                    Category.user_id == current_user.id,
                    Category.section == data["section"],
                    Category.name == data["category"]
                ).first()
                if not exists:
                    initial_budget = int(data.get("amount", 0) or 0)
                    add_category_to_db(db, current_user.id, data["section"], data["category"], initial_budget)
                    background_tasks.add_task(add_category_to_sheet, data["section"], data["category"], initial_budget)
                    final_action_taken = True
                    
                    if data["section"] == data["category"]:
                        msg = f"Carpeta '{data['section']}' creada. ¿Qué primera subcategoría tendrá?"
                        if "?" not in response_text: response_text = f"{response_text}. {msg}" if response_text else msg
                    else:
                        msg = f"Categoría '{data['category']}' creada en '{data['section']}'. ¿Qué presupuesto mensual tendrá?"
                        if "presupuesto" not in response_text.lower(): response_text = f"{response_text}. {msg}" if response_text else msg
                    aggregated_responses.append(response_text)
                else: aggregated_responses.append(f"Categoría {data['category']} ya existe.")
            elif data.get("section") and not data.get("category"):
                 aggregated_responses.append(f"Para crear la carpeta '{data['section']}', necesito saber qué primera subcategoría tendrá.")
            else: aggregated_responses.append("No entendí los datos para crear.")

        # J. ACTUALIZAR PRESUPUESTO GLOBAL
        elif intent == "UPDATE_GLOBAL_BUDGET":
            amount = data.get("amount")
            if amount:
                current_month = datetime.now().strftime("%Y-%m")
                budget_obj = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.month == current_month).first()
                if budget_obj: budget_obj.amount = int(amount)
                else:
                    budget_obj = Budget(user_id=current_user.id, month=current_month, amount=int(amount))
                    db.add(budget_obj)
                db.commit()
                final_action_taken = True
                aggregated_responses.append(response_text or f"Presupuesto mensual definido en ${int(amount):,}.")
            else: aggregated_responses.append("No entendí el presupuesto.")

        # D. CREAR GASTO (Default)
        else:
            try:
                # Verificación de duplicados: si la categoría existe en varias carpetas,
                # y el usuario NO mencionó explícitamente una carpeta, preguntar.
                all_matches = db.query(Category).filter(
                    Category.user_id == current_user.id,
                    Category.name == data["category"]
                ).all()
                
                if len(all_matches) > 1:
                    # Ver si el mensaje menciona alguna de las carpetas encontradas
                    match_found = None
                    for m in all_matches:
                        if m.section.lower() in user_msg.lower():
                            match_found = m
                            break
                    
                    if match_found:
                        data["section"] = match_found.section
                    else:
                        sects = ", ".join([f"'{c.section}'" for c in all_matches])
                        aggregated_responses.append(f"El ítem '{data['category']}' existe en varias carpetas: {sects}. ¿A cuál corresponde?")
                        continue 

                exists = db.query(Category).filter(Category.user_id == current_user.id, Category.section == data["section"], Category.name == data["category"]).first()
                if not exists:
                    add_category_to_db(db, current_user.id, data["section"], data["category"], 0)
                    try: background_tasks.add_task(add_category_to_sheet, data["section"], data["category"], 0)
                    except: pass

                new_expense = Expense(
                    user_id=current_user.id, amount=int(data["amount"]), concept=data["concept"],
                    category=data["category"], section=data["section"], payment_method=data["payment_method"], date=date.today()
                )
                db.add(new_expense)
                db.commit()
                
                expense_dict = {"date": str(new_expense.date), "concept": new_expense.concept, "category": new_expense.category, "amount": new_expense.amount, "payment_method": new_expense.payment_method}
                background_tasks.add_task(sync_expense_to_sheet, expense_dict, current_user.tecnico_nombre, section=data["section"])
                final_action_taken = True
                last_expense_data = expense_dict
                aggregated_responses.append(response_text or "Gasto registrado.")
            except Exception as e:
                aggregated_responses.append("Error registrando gasto.")

    final_msg_text = "\n".join(aggregated_responses) if aggregated_responses else "No entendí qué hacer."
    from app.models.models import ChatHistory
    db.add(ChatHistory(user_id=current_user.id, role="assistant", message=final_msg_text))
    db.commit()

    return ChatResponse(message=final_msg_text, action_taken=final_action_taken, expense_data=last_expense_data, intent="MULTI_ACTION")
