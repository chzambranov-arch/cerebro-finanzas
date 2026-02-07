import sys
import os

# Add parent directory to path to allow importing app module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.finance import Expense
from app.services.sheets_service import clear_expenses_sheet, update_monthly_budget as update_sheet_budget
from app.services.db_service import update_monthly_budget
from app.models.models import User

def reset_data():
    db = SessionLocal()
    try:
        print("Starting data reset...")
        
        # 1. Delete Local Expenses
        # Need to commit deletions explicitly
        num_deleted = db.query(Expense).delete()
        print(f"Deleted {num_deleted} expenses from local DB.")
        
        # 2. Reset Global Budget & Category Budgets
        from app.models.budget import Category
        users = db.query(User).all()
        for user in users:
            # Global Budget
            update_monthly_budget(db, user.id, 0)
            print(f"Reset global budget for user {user.tecnico_nombre}")
            
            # Category Budgets
            num_cats = db.query(Category).filter(Category.user_id == user.id).update({"budget": 0})
            print(f"Reset {num_cats} category budgets to 0 for user {user.tecnico_nombre}")
        
        db.commit()
        
        # 3. Clear Sheets
        print("Clearing 'Gastos' sheet...")
        if clear_expenses_sheet():
            print("Sheet 'Gastos' cleared.")
            
        # 4. Reset Sheet Budget
        update_sheet_budget(0)
        print("Sheet Budget reset to 0.")
        
        print("Data reset complete.")
        
    except Exception as e:
        print(f"Error during reset: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_data()
