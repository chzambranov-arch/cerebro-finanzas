from app.database import SessionLocal
# Import all models to ensure mappers are initialized properly
from app.models.models import User, ChatHistory
from app.models.finance import Expense
from app.models.budget import Budget

db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(f"ID: {u.id}, Name: {u.tecnico_nombre}, Email: {u.email}")
db.close()
