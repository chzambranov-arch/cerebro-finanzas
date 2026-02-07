
from app.database import SessionLocal
# Import all models to ensure mappers are configured
from app.models.models import User
from app.models.budget import Category, Budget
from app.models.finance import Expense, Commitment

# Query
db = SessionLocal()

print("Checking categories...")
users = db.query(User).all()

for u in users:
    print(f"User: {u.id} {u.email}")
    cats = db.query(Category).filter(Category.user_id == u.id).all()
    found = False
    for c in cats:
        if "casa" in c.section.lower() or "casa" in c.name.lower():
            print(f"  *** FOUND MATCH *** -> ID: {c.id} | Section: [{c.section}] | Name: {c.name}")
            found = True
    
    if not found:
        print("  User has NO 'Casa' related categories.")

db.close()
