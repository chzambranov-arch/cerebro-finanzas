import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.services.ai_service import process_finance_message

db = SessionLocal()
try:
    user_id = 2 # Christian ZV
    message = "borra el ultimo"
    print(f"Testing message: {message}")
    result = process_finance_message(db, user_id, message)
    print("RESULT:")
    import json
    print(json.dumps(result, indent=2))
finally:
    db.close()
