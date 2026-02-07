from app.database import SessionLocal
from app.models.models import User
from app.models.budget import Category, Budget
from app.models.finance import Expense, Commitment

db = SessionLocal()
print("All categories for Christian:")
user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
if user:
    cats = db.query(Category).filter(Category.user_id == user.id).all()
    for c in cats:
        print(f"ID: {c.id} | Section: [{c.section}] | Name: {c.name} | Budget: {c.budget}")
db.close()
