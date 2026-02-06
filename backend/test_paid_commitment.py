import os
import sys
import time
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

def test_paid_commitment():
    db = SessionLocal()
    bg = MockBackgroundTasks()
    
    unique_title = f"Deuda Test {int(time.time())}"
    
    try:
        user = db.query(User).filter(User.id == 2).first()
        
        # 1. Crear compromiso pendiente
        new_comm = Commitment(
            user_id=user.id,
            title=unique_title,
            type="DEBT",
            total_amount=7777,
            status="PENDING"
        )
        db.add(new_comm)
        db.commit()
        db.refresh(new_comm)
        print(f"Creado ID {new_comm.id}: {new_comm.title} | Status: {new_comm.status}")

        print("\n--- COMPROMISOS EN DB PARA CONTEXTO ---")
        comms = db.query(Commitment).filter(Commitment.user_id == user.id).order_by(Commitment.id.desc()).limit(5).all()
        for c in comms:
            print(f"ID: {c.id} | {c.title} | {c.status}")

        # 2. Pedir a Lucio que lo marque como pagado
        req = ChatRequest(message=f"Ya pague lo de {unique_title}")
        print(f"\n--- ENVIANDO MENSAJE: {req.message} ---")
        res = chat_with_agent(req, bg, db, user)
        print(f"Respuesta Lucio: {res.message}")
        print(f"Intent detectado: {res.intent}")

        # 3. Verificar en DB
        db.expire_all()
        db.refresh(new_comm)
        print(f"\nSTATUS FINAL EN DB: {new_comm.status}")
        
        if new_comm.status == "PAID":
            print("\nTEST EXITOSO: El compromiso se marco como pagado.")
        else:
            print(f"\nTEST FALLIDO: El status sigue siendo {new_comm.status}")

    finally:
        db.close()

if __name__ == "__main__":
    test_paid_commitment()
