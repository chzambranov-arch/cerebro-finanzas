from app.database import SessionLocal
from app.models.finance import PendingExpense, PushSubscription
from app.models.models import User

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
    if user:
        print(f"User ID: {user.id}")
        pendings = db.query(PendingExpense).filter(PendingExpense.user_id == user.id, PendingExpense.status == "PENDING").all()
        print(f"Pending Expenses: {len(pendings)}")
        for p in pendings:
            print(f" - ID: {p.id} | Concept: {p.concept} | Amount: {p.amount}")
            
        subs = db.query(PushSubscription).filter(PushSubscription.user_id == user.id).all()
        print(f"Push Subscriptions: {len(subs)}")
        for s in subs:
            print(f" - ID: {s.id} | Endpoint: {s.endpoint[:50]}...")
    else:
        print("User not found.")
finally:
    db.close()
