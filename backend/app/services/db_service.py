from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from typing import Optional, Dict, List
from app.models.finance import Folder, Item, Expense, ExpenseType, ChatHistory
from app.models.user import User
from app.schemas import FolderSummary, DashboardData

# --- FOLDER SERVICES ---

def get_folders(db: Session, user_id: int):
    return db.query(Folder).filter(Folder.user_id == user_id).all()

def create_folder(db: Session, user_id: int, name: str, initial_balance: int):
    # Search for existing
    existing = db.query(Folder).filter(Folder.user_id == user_id, Folder.name == name).first()
    if existing:
        return existing
    
    new_folder = Folder(user_id=user_id, name=name, initial_balance=initial_balance)
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

def update_folder(db: Session, folder_id: int, name: Optional[str] = None, initial_balance: Optional[int] = None):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        return None
    if name:
        folder.name = name
    if initial_balance is not None:
        folder.initial_balance = initial_balance
    db.commit()
    db.refresh(folder)
    return folder

# --- ITEM SERVICES ---

def create_item(db: Session, folder_id: int, name: str, budget: int, type: ExpenseType):
    new_item = Item(folder_id=folder_id, name=name, budget=budget, type=type)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

# --- EXPENSE SERVICES ---

def create_expense(db: Session, user_id: int, description: str, amount: int, folder_id: int, 
                   type: ExpenseType, item_id: Optional[int] = None, date_obj: Optional[date] = None):
    if not date_obj:
        date_obj = date.today()
        
    new_expense = Expense(
        user_id=user_id,
        description=description,
        amount=amount,
        folder_id=folder_id,
        item_id=item_id,
        type=type,
        date=date_obj
    )
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense

# --- DASHBOARD & LOGIC ---

def get_dashboard_summary(db: Session, user_id: int):
    folders = db.query(Folder).filter(Folder.user_id == user_id).all()
    
    total_budget = 0
    total_spent = 0
    folder_summaries = []
    
    current_month_first_day = date.today().replace(day=1)
    
    for folder in folders:
        total_budget += folder.initial_balance
        
        # Spent in this folder this month
        spent_in_folder = db.query(func.sum(Expense.amount)).filter(
            Expense.folder_id == folder.id,
            Expense.date >= current_month_first_day
        ).scalar() or 0
        
        total_spent += spent_in_folder
        
        # Detailed items for this folder (optional if needed by UI)
        # But for the summary we just need spent/remaining
        summary = {
            "id": folder.id,
            "name": folder.name,
            "initial_balance": folder.initial_balance,
            "spent": spent_in_folder,
            "remaining": folder.initial_balance - spent_in_folder
        }
        folder_summaries.append(summary)
        
    user = db.query(User).filter(User.id == user_id).first()
    user_name = user.tecnico_nombre if user else "Usuario"
    
    return {
        "user_name": user_name,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "folders": folder_summaries
    }

def get_folder_details(db: Session, folder_id: int):
    """Obtiene detalles de una carpeta, incluyendo ítems y su consumo"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        return None
        
    current_month_first_day = date.today().replace(day=1)
    
    # Items categorized or sporadic
    items_data = []
    items = db.query(Item).filter(Item.folder_id == folder_id).all()
    
    for item in items:
        spent_on_item = db.query(func.sum(Expense.amount)).filter(
            Expense.item_id == item.id,
            Expense.date >= current_month_first_day
        ).scalar() or 0
        
        items_data.append({
            "id": item.id,
            "name": item.name,
            "budget": item.budget,
            "spent": spent_on_item,
            "remaining": item.budget - spent_on_item,
            "type": item.type,
            "is_paid": (item.type == ExpenseType.FIJO and spent_on_item > 0)
        })
        
    # Sporadic expenses in this folder
    sporadic_expenses_query = db.query(Expense).filter(
        Expense.folder_id == folder_id,
        Expense.item_id == None,
        Expense.date >= current_month_first_day
    )
    
    sporadic_spent = db.query(func.sum(Expense.amount)).filter(
        Expense.folder_id == folder_id,
        Expense.item_id == None,
        Expense.date >= current_month_first_day
    ).scalar() or 0
    
    sporadic_items = []
    for exp in sporadic_expenses_query.all():
         sporadic_items.append({
             "id": exp.id,
             "description": exp.description,
             "amount": exp.amount,
             "date": exp.date
         })
    
    return {
        "id": folder.id,
        "name": folder.name,
        "initial_balance": folder.initial_balance,
        "items": items_data,
        "sporadic_spent": sporadic_spent,
        "sporadic_items": sporadic_items
    }

def delete_folder(db: Session, folder_id: int):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if folder:
        # Cascade delete is handled by SQLAlchemy if configured, but let's be explicit if needed
        # Actually our models.finance should have cascade
        db.delete(folder)
        db.commit()
        return True
    return False

def delete_item(db: Session, item_id: int):
    item = db.query(Item).filter(Item.id == item_id).first()
    if item:
        # Manually cascade delete expenses for this item
        db.query(Expense).filter(Expense.item_id == item_id).delete(synchronize_session=False)
        db.delete(item)
        db.commit()
        return True
    return False

def delete_sporadic_expenses(db: Session, folder_id: int):
    try:
        db.query(Expense).filter(
            Expense.folder_id == folder_id,
            Expense.item_id == None
        ).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception as e:
        print(f"Error deleing sporadic: {e}")
        db.rollback()
        return False

def delete_expense(db: Session, expense_id: int):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False

# --- CHAT MEMORY ---

def add_chat_msg(db: Session, user_id: int, role: str, message: str):
    msg = ChatHistory(user_id=user_id, role=role, message=message)
    db.add(msg)
    db.commit()

def get_chat_history(db: Session, user_id: int, limit: int = 5):
    return db.query(ChatHistory).filter(ChatHistory.user_id == user_id).order_by(ChatHistory.timestamp.desc()).limit(limit).all()
