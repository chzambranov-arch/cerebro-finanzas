import sys
import os

# Add the parent directory to sys.path so we can import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.database import SessionLocal, engine, Base
from app.models.finance import Expense, Commitment, PendingExpense
from app.models.budget import Budget, Category
from app.models.models import ChatHistory, User
from sqlalchemy.orm import Session

def wipe_data():
    db = SessionLocal()
    try:
        # Looking for user explicitly
        user = db.query(User).filter(User.tecnico_nombre == "Christian ZV").first()
        if not user:
             user = db.query(User).filter(User.id == 2).first()
        
        if not user:
            print("User ID 2 ('Christian ZV') not found.")
            return

        user_id = user.id
        print(f"Wiping data for user {user.tecnico_nombre} (ID: {user_id})...")

        # 1. Expenses
        num = db.query(Expense).filter(Expense.user_id == user_id).delete()
        print(f"Deleted {num} expenses.")

        # 2. Commitments
        num = db.query(Commitment).filter(Commitment.user_id == user_id).delete()
        print(f"Deleted {num} commitments.")

        # 3. Pending Expenses
        num = db.query(PendingExpense).filter(PendingExpense.user_id == user_id).delete()
        print(f"Deleted {num} pending expenses.")

        # 4. Categories
        num = db.query(Category).filter(Category.user_id == user_id).delete()
        print(f"Deleted {num} categories.")

        # 5. Budgets
        num = db.query(Budget).filter(Budget.user_id == user_id).delete()
        print(f"Deleted {num} budgets.")

        # 6. Chat History
        num = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
        print(f"Deleted {num} chat messages.")
        
        db.commit()
        print("Data wipe complete.")
    
    except Exception as e:
        print(f"Error wiping data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    wipe_data()
