import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.models.models import User
from app.models.finance import Expense
from app.models.budget import Category

db = SessionLocal()
try:
    uid = 2
    exps = db.query(Expense).filter(Expense.user_id == uid).order_by(Expense.id.desc()).all()
    print(f"TOTAL EXPENSES FOR UID 2: {len(exps)}")
    for e in exps[:10]:
        print(f"ID: {e.id} | {e.date} | ${e.amount} | {e.concept}")
finally:
    db.close()
