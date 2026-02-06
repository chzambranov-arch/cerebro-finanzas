import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.models.models import User
from app.models.finance import Commitment
from app.routers.agent import chat_with_agent, ChatRequest

class MockBackgroundTasks:
    def add_task(self, func, *args, **kwargs):
        print(f"DEBUG [MOCK] Background task: {func.__name__}")

def test_commitment_flow():
    db = SessionLocal()
    bg = MockBackgroundTasks()
    try:
        user = db.query(User).filter(User.id == 2).first()
        
        # Test 1: "Debo 5000 a Pedro"
        req = ChatRequest(message="Debo 5000 a Pedro")
        print(f"\n--- TEST 1: {req.message} ---")
        res = chat_with_agent(req, bg, db, user)
        print(f"Respuesta: {res.message}")
        print(f"Intent: {res.intent}")
        
        # Check if created
        last_comm = db.query(Commitment).filter(Commitment.user_id == 2).order_by(Commitment.id.desc()).first()
        print(f"DB -> ID: {last_comm.id}, Title: {last_comm.title}, Type: {last_comm.type}, Amount: {last_comm.total_amount}")

        # Test 2: "Juan me debe 10000"
        req2 = ChatRequest(message="Juan me debe 10000")
        print(f"\n--- TEST 2: {req2.message} ---")
        res2 = chat_with_agent(req2, bg, db, user)
        print(f"Respuesta: {res2.message}")
        print(f"Intent: {res2.intent}")
        
        last_comm2 = db.query(Commitment).filter(Commitment.user_id == 2).order_by(Commitment.id.desc()).first()
        print(f"DB -> ID: {last_comm2.id}, Title: {last_comm2.title}, Type: {last_comm2.type}, Amount: {last_comm2.total_amount}")

        # Test 3: "Borra la deuda de Juan"
        req3 = ChatRequest(message="Borra el compromiso de Juan")
        print(f"\n--- TEST 3: {req3.message} ---")
        res3 = chat_with_agent(req3, bg, db, user)
        print(f"Respuesta: {res3.message}")
        print(f"Intent: {res3.intent}")

    finally:
        db.close()

if __name__ == "__main__":
    test_commitment_flow()
