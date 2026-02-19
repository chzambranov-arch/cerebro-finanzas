import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.services import db_service
from app.models.finance import Item, Expense

db = SessionLocal()
try:
    # Simulate what the endpoint does
    item_id = 2
    item = db.query(Item).filter(Item.id == item_id).first()
    print(f"Item found: {item}")
    if item:
        print(f"  folder_id: {item.folder_id}")
        # Delete expenses first
        deleted = db.query(Expense).filter(Expense.item_id == item_id).delete(synchronize_session=False)
        print(f"  Deleted {deleted} expenses")
        db.delete(item)
        db.commit()
        print("  Item deleted successfully")
    else:
        print("  Item not found")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
