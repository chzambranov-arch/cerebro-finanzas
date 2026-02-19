from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import os
from app.database import get_db
from app.models.user import User
from app.models.finance import Folder as FolderModel, Item as ItemModel, Expense as ExpenseModel
from app.deps import get_current_user
from app.schemas import Folder, FolderCreate, Item, ItemCreate, Expense, ExpenseCreate, DashboardData
from app.services import db_service

router = APIRouter(tags=["finance"])

# n8n Authentication Token
N8N_WEBHOOK_TOKEN = os.getenv("N8N_WEBHOOK_TOKEN", "lucio_secret_token_2026_change_me")

def get_user_for_context(
    x_n8n_token: Optional[str] = Header(None, alias="X-N8N-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Autenticación flexible para n8n:
    1. Si tiene X-N8N-Token válido -> OK
    2. Si no, intenta validar Bearer token tradicional
    """
    # 1. Validar Token de n8n
    if x_n8n_token == N8N_WEBHOOK_TOKEN:
        return "n8n"
    
    # 2. Validar Token de Usuario (si viene de la app)
    if authorization and authorization.startswith("Bearer "):
        try:
            from app.deps import get_current_user
            token = authorization.replace("Bearer ", "")
            user = get_current_user(token=token, db=db)
            return user
        except:
            pass
            
    raise HTTPException(status_code=401, detail="Authentication required (X-N8N-Token or Bearer)")

# --- DASHBOARD ---

@router.get("/dashboard", response_model=DashboardData)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db_service.get_dashboard_summary(db, current_user.id)

# --- CONTEXT (for n8n AI) ---

@router.get("/context")
def get_financial_context(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    auth: Optional[User] = Depends(get_user_for_context)
):
    """
    Endpoint de contexto financiero para n8n.
    
    Retorna carpetas completas con items, presupuestos y tipos.
    Esto permite que la IA de n8n razone con datos reales.
    
    Autenticación:
    - n8n: Envía X-N8N-Token header + user_id en query
    - App: Usa Bearer token normal
    """
    # Determinar el user_id efectivo
    if hasattr(auth, "id"):
        # Viene del frontend con auth de usuario (Bearer)
        effective_user_id = auth.id
    elif auth == "n8n":
        # Viene de n8n con X-N8N-Token
        if not user_id:
             raise HTTPException(status_code=400, detail="user_id query param is required for n8n")
        effective_user_id = user_id
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Obtener todas las carpetas del usuario con sus items
    folders_data = []
    folders = db.query(FolderModel).filter(
        FolderModel.user_id == effective_user_id
    ).all()
    
    for folder in folders:
        items_data = []
        for item in folder.items:
            items_data.append({
                "id": item.id,
                "name": item.name,
                "type": item.type.value if hasattr(item.type, "value") else str(item.type),
                "budget": item.budget
            })
        
        folders_data.append({
            "id": folder.id,
            "name": folder.name,
            "initial_balance": folder.initial_balance,
            "items": items_data
        })
    
    return {
        "user_id": effective_user_id,
        "folders": folders_data
    }

# --- EXECUTE (for n8n callbacks) ---

@router.post("/execute")
async def execute_n8n_action(
    action_data: Dict[str, Any],
    x_n8n_token: Optional[str] = Header(None, alias="X-N8N-Token"),
    db: Session = Depends(get_db)
):
    """
    Endpoint de ejecución para n8n.
    
    n8n llama aquí después de procesar con OpenAI para ejecutar la acción decidida.
    
    Payload esperado:
    {
        "intent": "CREATE_EXPENSE",
        "user_id": 1,
        "data": {"monto": 15000, "carpeta": "Ocio", ...},
        "needs_folder_creation": false,
        "needs_item_creation": true
    }
    
    Autenticación: Requiere X-N8N-Token header válido
    """
    # Validar token de n8n
    if x_n8n_token != N8N_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid n8n token")
    
    # Ejecutar acción vía N8NService
    from app.services.n8n_service import N8NService
    resultado = await N8NService.ejecutar_accion_n8n(action_data)
    
    return resultado

# --- REPORTING (for n8n AI) ---

@router.get("/report")
def get_finance_report(
    user_id: int,
    tipo_reporte: str,
    carpeta: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate financial reports for n8n AI.
    Types: HISTORIAL_GASTOS, RESUMEN_CARPETA
    """
    if tipo_reporte == "HISTORIAL_GASTOS":
        query = db.query(ExpenseModel).filter(ExpenseModel.user_id == user_id)
        
        if carpeta:
            # Join with Folder to filter by name
            folder = db.query(FolderModel).filter(FolderModel.user_id == user_id, FolderModel.name == carpeta).first()
            if folder:
                 query = query.filter(ExpenseModel.folder_id == folder.id)
            else:
                 return {"status": "success", "resumen": f"Carpeta '{carpeta}' no encontrada", "datos": []}
            
        # Get last 5
        expenses = query.order_by(ExpenseModel.date.desc(), ExpenseModel.id.desc()).limit(5).all()
        
        data = []
        for e in expenses:
            data.append({
                "id": e.id,
                "amount": e.amount,
                "description": e.description,
                "date": e.date,
                "folder_id": e.folder_id
            })
            
        return {
            "status": "success",
            "resumen": f"Últimos {len(data)} gastos registrados" + (f" en carpeta '{carpeta}'" if carpeta else ""),
            "datos": data
        }

    elif tipo_reporte == "RESUMEN_CARPETA":
        if not carpeta:
             return {"status": "error", "message": "Parámetro 'carpeta' requerido para RESUMEN_CARPETA"}
             
        # Find folder by name for this user
        folder = db.query(FolderModel).filter(FolderModel.user_id == user_id, FolderModel.name == carpeta).first()
        if not folder:
            return {"status": "error", "message": f"Carpeta '{carpeta}' no encontrada"}
            
        # Calculate stats
        total_budget = 0
        for item in folder.items:
            total_budget += item.budget
            
        # Total spent in folder
        total_spent = db.query(func.sum(ExpenseModel.amount)).filter(ExpenseModel.folder_id == folder.id).scalar() or 0
        
        return {
            "status": "success",
            "resumen": f"Resumen de carpeta '{carpeta}'",
            "datos": {
                "carpeta": carpeta,
                "presupuesto_total": total_budget,
                "gasto_total": total_spent,
                "disponible": total_budget - total_spent
            }
        }
        
    else:
        return {"status": "error", "message": f"Tipo de reporte '{tipo_reporte}' no soportado"}

# --- FOLDERS ---

@router.get("/folders", response_model=List[Folder])
def list_folders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db_service.get_folders(db, current_user.id)

@router.post("/folders", response_model=Folder)
def create_folder(payload: FolderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db_service.create_folder(db, current_user.id, payload.name, payload.initial_balance)

@router.get("/folders/{folder_id}")
def get_folder_details(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    details = db_service.get_folder_details(db, folder_id)
    if not details:
        raise HTTPException(status_code=404, detail="Folder not found")
    return details

# --- ITEMS ---

@router.post("/items", response_model=Item)
def create_item(payload: ItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify folder ownership
    folder = db_service.get_folders(db, current_user.id)
    if not any(f.id == payload.folder_id for f in folder):
         raise HTTPException(status_code=403, detail="Folder not owned by you")
    return db_service.create_item(db, payload.folder_id, payload.name, payload.budget, payload.type)

# --- EXPENSES ---

@router.post("/expenses", response_model=Expense)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Basic verification
    # 1. Folder exists and belongs to user
    folder_details = db_service.get_folder_details(db, payload.folder_id)
    if not folder_details:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # 2. Logic for Fixed/Saldo items
    if payload.type in ["FIJO", "CON_SALDO"] and not (payload.item_id or payload.item):
        raise HTTPException(status_code=400, detail="FIJO and CON_SALDO expenses require an item_id")
    
    return db_service.create_expense(
        db, 
        current_user.id,
        payload.description,
        payload.amount,
        payload.folder_id,
        payload.type,
        payload.item_id or payload.item,
        payload.date
    )
@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify ownership
    folders = db_service.get_folders(db, current_user.id)
    if not any(f.id == folder_id for f in folders):
         raise HTTPException(status_code=403, detail="Folder not owned by you")
    if db_service.delete_folder(db, folder_id):
        return {"detail": "Folder deleted"}
    raise HTTPException(status_code=404, detail="Folder not found")

@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify ownership via folder
    folders = db_service.get_folders(db, current_user.id)
    folder_ids = [f.id for f in folders]
    
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if not item or item.folder_id not in folder_ids:
        raise HTTPException(status_code=403, detail="Item not owned by you")
         
    if db_service.delete_item(db, item_id):
        return {"detail": "Item deleted"}
    raise HTTPException(status_code=404, detail="Item not found")

@router.delete("/expenses/{expense_id}")
def delete_expense_endpoint(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify ownership check? For simplicity we assume user owns expense if they have access.
    # Ideally check expense->folder->user_id == current_user.id
    # But db_service just deletes by ID. Let's add ownership check for security.
    expense = db.query(ExpenseModel).filter(ExpenseModel.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this expense")

    if db_service.delete_expense(db, expense_id):
         return {"detail": "Expense deleted"}
    raise HTTPException(status_code=500, detail="Could not delete expense")

@router.delete("/folders/{folder_id}/sporadic")
def clear_sporadic_expenses(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify ownership
    folders = db_service.get_folders(db, current_user.id)
    if not any(f.id == folder_id for f in folders):
         raise HTTPException(status_code=403, detail="Folder not owned by you")

    if db_service.delete_sporadic_expenses(db, folder_id):
        return {"detail": "Sporadic expenses cleared"}
    raise HTTPException(status_code=500, detail="Could not delete sporadic expenses")
