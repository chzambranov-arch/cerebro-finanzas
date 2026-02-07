from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import date
from app.database import get_db
from app.models.models import User, Role
from app.models.finance import Expense
from app.deps import get_current_user
from app.services.sheets_service import sync_expense_to_sheet, get_dashboard_data

router = APIRouter(tags=["finance"])

# --- Pydantic Schemas ---
class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    amount: int
    concept: str
    category: str
    section: Optional[str] = "OTROS"
    date: date
    payment_method: Optional[str] = None
    image_url: Optional[str] = None

# --- Endpoints ---

@router.post("/", response_model=ExpenseOut)
def create_expense(
    background_tasks: BackgroundTasks,
    amount: int = Form(...),
    concept: str = Form(None),
    category: str = Form(...),
    payment_method: str = Form(...),
    section: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new expense linked to the authenticated user.
    """
    try:
        user = current_user

        image_url = None
        if image:
            import os
            import shutil
            from datetime import datetime
            
            upload_dir = "uploads/receipts"
            os.makedirs(upload_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{user.tecnico_nombre}_{timestamp}_{image.filename}"
            file_path = f"{upload_dir}/{filename}"
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            image_url = f"/uploads/receipts/{filename}"

        new_expense = Expense(
            user_id=user.id,
            amount=amount,
            concept=concept or "Gasto sin concepto",
            category=category,
            section=section,
            payment_method=payment_method,
            date=date.today(),
            image_url=image_url
        )
        db.add(new_expense)
        db.commit()
        db.refresh(new_expense)
        
        # Preparar data para sync opcional a Sheets (background)
        expense_data = {
            "date": str(new_expense.date),
            "concept": new_expense.concept,
            "category": new_expense.category,
            "amount": new_expense.amount,
            "payment_method": new_expense.payment_method,
            "image_url": new_expense.image_url
        }
        
        # Sync opcional a Sheets (no bloqueante, se ignora si falla)
        try:
            background_tasks.add_task(sync_expense_to_sheet, expense_data, user.tecnico_nombre, section=section)
        except Exception as e:
            print(f"WARNING: Optional Sheets sync failed (ignoring): {e}")
        
        return new_expense
        
    except Exception as e:
        print(f"Error creating expense: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an expense.
    """
    from app.services.sheets_service import delete_expense_from_sheet
    
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found or not owned by you")

    # Prepare data for sheets deletion
    expense_data = {
        "date": str(expense.date),
        "concept": expense.concept,
        "amount": expense.amount
    }
    
    # BEST EFFORT: Delete from Sheets
    # We try to delete from Sheets, but if it fails (e.g. no match found, row locked),
    # we MUST still delete from the local DB so the user sees it gone.
    try:
        delete_expense_from_sheet(expense_data, current_user.tecnico_nombre)
    except Exception as e:
        print(f"WARNING [DELETE] Failed to delete from Sheets (ignoring): {e}")

    # TRANSACTION: Delete from Local DB
    try:
        db.delete(expense)
        db.commit()
        return {"message": "Expense deleted successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error deleting expense from DB: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ExpenseOut])
def get_my_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all expenses. If DB is empty, attempts to restore from Sheets.
    """
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).order_by(Expense.id.desc()).all()
    
    if not expenses:
        print("DEBUG [DB] Database empty. Fetching from Sheets...")
        try:
            from app.services.sheets_service import get_all_expenses_from_sheet
            sheet_expenses = get_all_expenses_from_sheet()
            
            if sheet_expenses:
                for exp_data in sheet_expenses:
                    new_expense = Expense(
                        user_id=current_user.id,
                        date=exp_data["date"],
                        concept=exp_data["concept"],
                        category=exp_data["category"],
                        amount=exp_data["amount"],
                        payment_method=exp_data["payment_method"],
                        image_url=exp_data["image_url"],
                        section="OTROS"
                    )
                    db.add(new_expense)
                
                db.commit()
                # Query again strictly for this user
                expenses = db.query(Expense).filter(Expense.user_id == current_user.id).order_by(Expense.id.desc()).all()
                print(f"DEBUG [DB] Restored {len(expenses)} expenses from Sheets.")
        except Exception as e:
            print(f"ERROR [DB] Emergency sync failed: {e}")
            
    return expenses

@router.post("/sync-force")
def force_sync_from_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Force full resync from Google Sheets.
    WARNING: This deletes local expenses and re-fetches everything from 'Gastos' sheet.
    """
    try:
        # 1. Delete all local expenses (Nuclear Option)
        db.query(Expense).delete()
        db.commit()
        print("DEBUG [SYNC] Local expenses cleared.")
        
        # 2. Fetch all from Sheets
        from app.services.sheets_service import get_all_expenses_from_sheet
        sheet_expenses = get_all_expenses_from_sheet()
        
        count = 0
        if sheet_expenses:
            for exp_data in sheet_expenses:
                new_expense = Expense(
                    user_id=current_user.id,
                    date=exp_data["date"],
                    concept=exp_data["concept"],
                    category=exp_data["category"],
                    section=exp_data.get("section", "OTROS"), # Now catching section
                    amount=exp_data["amount"],
                    payment_method=exp_data["payment_method"],
                    image_url=exp_data["image_url"]
                )
                db.add(new_expense)
                count += 1
            
            db.commit()
            print(f"DEBUG [SYNC] Restored {count} expenses from Sheets.")
            
        return {"message": f"Sincronización forzada completada. {count} gastos recuperados.", "count": count}
        
    except Exception as e:
        print(f"ERROR [SYNC] Force sync failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard")
def get_finance_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dashboard summary data for the authenticated user from DATABASE.
    Automatically initializes default data if needed.
    """
    from app.services.db_service import (
        get_dashboard_data_from_db, 
        initialize_default_categories,
        update_monthly_budget,
        update_category_in_db
    )
    from app.models.budget import Category, Budget
    
    # Auto-inicializar si no tiene datos
    has_budget = db.query(Budget).filter(Budget.user_id == current_user.id).first()
    has_categories = db.query(Category).filter(Category.user_id == current_user.id).first()
    
    # [AUTO-INIT DISABLED FOR CLEAN SLATE TESTING]
    # if not has_budget:
    #     print(f"[AUTO-INIT] Creating default budget for user {current_user.id}")
    #     update_monthly_budget(db, current_user.id, 500000)
    
    # if not has_categories:
    #     print(f"[AUTO-INIT] Creating default categories for user {current_user.id}")
    #     initialize_default_categories(db, current_user.id)
        
    #     # Actualizar con presupuestos reales
    #     categories_with_budget = [
    #         ("CASA", "Arriendo", 200000),
    #         ("CASA", "Servicios", 50000),
    #         ("CASA", "Supermercado", 100000),
    #         ("FAMILIA", "Salud", 30000),
    #         ("FAMILIA", "Educación", 20000),
    #         ("TRANSPORTE", "Bencina", 40000),
    #         ("TRANSPORTE", "Uber", 20000),
    #     ]
        
    #     for section, category, budget in categories_with_budget:
    #         try:
    #             update_category_in_db(db, current_user.id, section, category, new_budget=budget)
    #         except:
    #             pass  # Ignorar si falla
    
    data = get_dashboard_data_from_db(db, current_user.id)
    return data

# --- Category Management ---

class CategoryCreate(BaseModel):
    section: str
    category: str
    budget: int = 0

class CategoryDelete(BaseModel):
    section: str
    category: str

@router.post("/categories/")
def create_category_endpoint(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a new subcategory to a section in DATABASE and Sync to SHEETS.
    """
    from app.services.db_service import add_category_to_db
    from app.services.sheets_service import add_category_to_sheet
    
    # 1. DB (Primary)
    success = add_category_to_db(db, current_user.id, payload.section, payload.category, payload.budget)
    if not success:
        # Check if it really exists or if it was just a conflict.
        # For now, return error.
        raise HTTPException(status_code=400, detail="Category already exists")

    # 2. Sheets (Sync)
    try:
        add_category_to_sheet(payload.section, payload.category, payload.budget)
    except Exception as e:
        print(f"WARNING: Sheets sync for new category failed: {e}")

    return {"message": "Category added successfully"}

@router.delete("/categories/")
def delete_category_endpoint(
    payload: CategoryDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a subcategory from DATABASE and SHEETS, but only if it has no expenses.
    """
    from app.services.db_service import delete_category_from_db
    from app.services.sheets_service import delete_category_from_sheet
    
    # 1. DB
    success = delete_category_from_db(db, current_user.id, payload.section, payload.category)
    if not success:
        raise HTTPException(status_code=400, detail="No se puede borrar: tiene gastos asociados o no existe")

    # 2. Sheets
    try:
        delete_category_from_sheet(payload.section, payload.category)
    except Exception as e:
        print(f"WARNING: Sheets sync for delete category failed: {e}")

    return {"message": "Category deleted successfully"}

class CategoryUpdate(BaseModel):
    section: str
    category: str
    new_budget: int
    new_category: Optional[str] = None

@router.patch("/categories/")
def update_category_endpoint(
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a subcategory's budget in DATABASE and SHEETS, and optionally rename it.
    """
    from app.services.db_service import update_category_in_db
    from app.services.sheets_service import update_category_in_sheet
    
    # 1. DB
    success = update_category_in_db(
        db, 
        current_user.id, 
        payload.section, 
        payload.category, 
        new_name=payload.new_category,
        new_budget=payload.new_budget
    )
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # 2. Sheets
    try:
        update_category_in_sheet(
            payload.section, 
            payload.category, 
            payload.new_budget, 
            new_cat=payload.new_category
        )
    except Exception as e:
        print(f"WARNING: Sheets sync for update category failed: {e}")

    return {"message": "Category updated successfully", "new_category": payload.new_category or payload.category}

class UpdateBudgetSchema(BaseModel):
    new_budget: int

@router.post("/budget")
def update_global_budget_endpoint(
    payload: UpdateBudgetSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the global monthly budget in DATABASE.
    """
    from app.services.db_service import update_monthly_budget
    success = update_monthly_budget(db, current_user.id, payload.new_budget)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update budget")
    return {"message": "Budget updated successfully", "new_budget": payload.new_budget}

# --- Gmail Sync ---

@router.post("/sync-gmail")
def sync_gmail_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger manual synchronization with Gmail to find new bank expenses.
    Requires 'gmail_credentials.json' to be present on the server.
    """
    from app.services.gmail_service import process_recent_emails
    
    result = process_recent_emails(db, current_user.id, current_user.tecnico_nombre)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["detail"])
        
    return result

@router.post("/reset-data")
def reset_all_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    NUCLEAR OPTION: Resets all financial data to 0.
    1. Deletes all local expenses.
    2. Clears 'Gastos' sheet in Google Sheets.
    3. Resets monthly budget to 0 (Local & Sheet).
    """
    from app.services.sheets_service import clear_expenses_sheet, update_monthly_budget as update_sheet_budget
    from app.services.db_service import update_monthly_budget
    from app.models.finance import Expense
    
    try:
        # 1. Delete Local Expenses
        num_deleted = db.query(Expense).delete()
        
        # 2. Reset Local Budget
        update_monthly_budget(db, current_user.id, 0)
        
        db.commit()
        print(f"DEBUG [RESET] Deleted {num_deleted} local expenses and reset budget.")
        
        # 3. Clear Sheets (Best Effort)
        try:
            clear_expenses_sheet()
            update_sheet_budget(0)
        except Exception as e:
            print(f"WARNING [RESET] Failed to clear sheets completely: {e}")
            
        return {"message": "All data has been reset to 0.", "deleted_count": num_deleted}
        
    except Exception as e:
        db.rollback()
        print(f"ERROR [RESET] Failed to reset data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
