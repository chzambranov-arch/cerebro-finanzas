import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.models.models import User
from app.models.finance import Expense

db = SessionLocal()
try:
    uid = 2 # Christian ZV
    exps = db.query(Expense).filter(Expense.user_id == uid).order_by(Expense.id.desc()).all()
    print(f"DEBUG LOCAL - TOTAL GASTOS (UID 2): {len(exps)}")
    for e in exps[:5]:
        print(f"ID: {e.id} | UserID: {e.user_id} | Concepto: {e.concept} | Monto: {e.amount}")
finally:
    db.close()
