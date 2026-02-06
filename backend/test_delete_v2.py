import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.services.ai_service import process_finance_message

with open("delete_test_utf8.json", "w", encoding="utf-8") as f:
    db = SessionLocal()
    try:
        user_id = 2 # Christian ZV
        message = "borra el ultimo"
        result = process_finance_message(db, user_id, message)
        f.write(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        db.close()
