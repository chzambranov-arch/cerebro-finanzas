
from app.database import SessionLocal
# Import ALL models that reference Base to ensure mappers are configured correctly.
# This prevents "mapper dependency" errors.
from app.models.models import User
from app.models.budget import Category, Budget
from app.models.finance import Expense, Commitment

db = SessionLocal()
user_email = "christian.zv@cerebro.com"
user = db.query(User).filter(User.email == user_email).first()

if not user:
    # Try finding the user by substring if exact match fails, or list all users
    all_users = db.query(User).all()
    print("Listing all users:")
    for u in all_users:
        print(f"ID: {u.id}, Email: {u.email}")
    
    # Try with first user if present
    if all_users:
        user = all_users[0]
        print(f"Using user: {user.email}")

if user:
    print(f"User ID: {user.id}")
    categories = db.query(Category).filter(Category.user_id == user.id).all()
    
    # Use set to get unique sections
    sections = set([c.section for c in categories])
    sections_list = ", ".join(sections)
    print(f"\nSECTIONS LIST:\n[{sections_list}]")
    
    print("\nCATEGORY HIERARCHY:")
    cat_context = "\n".join([f"- [{c.section}] -> {c.name}" for c in categories])
    print(cat_context)

db.close()
