
from app.database import SessionLocal
from app.models.models import User
from app.services.db_service import get_dashboard_data_from_db
import json

db = SessionLocal()
user_email = "christian.zv@cerebro.com"
user = db.query(User).filter(User.email == user_email).first()

if not user:
    print(f"User {user_email} not found. Trying first available user.")
    user = db.query(User).first()

if user:
    print(f"Checking dashboard data for User ID: {user.id}")
    try:
        data = get_dashboard_data_from_db(db, user.id)
        print(f"GLOBAL BUDGET: {data.get('monthly_budget')}")
        print(f"TOTAL SPENT: {data.get('total_spent')}")
        print(f"REMAINING: {data.get('remaining_budget')}")
        # print(json.dumps(data, indent=2, default=str)) # Commented out to reduce noise
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No users found in database.")

db.close()
