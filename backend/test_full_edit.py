import os
import sys
import json
from datetime import date
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.join(os.getcwd()))
from app.database import SessionLocal
from app.models.finance import Expense
from app.routers.agent import chat_with_agent, ChatRequest
from app.models.models import User

class MockBackgroundTasks:
    def add_task(self, func, *args, **kwargs):
        print(f"DEBUG [MOCK] Background task added: {func.__name__}")

def test_edit_flow():
    db = SessionLocal()
    bg = MockBackgroundTasks()
    try:
        user = db.query(User).filter(User.id == 2).first()
        if not user:
            print("ERROR: User ID 2 not found")
            return

        # 1. Crear un gasto de prueba
        test_expense = Expense(
            user_id=user.id,
            amount=5000,
            concept="Prueba Edit",
            category="General",
            section="OTROS",
            payment_method="DEBITO",
            date=date.today()
        )
        db.add(test_expense)
        db.commit()
        db.refresh(test_expense)
        exp_id = test_expense.id
        print(f"--- GASTO CREADO: ID={exp_id}, Monto=5000, Concepto='Prueba Edit' ---")

        # 2. Llamar al endpoint de chat
        request = ChatRequest(message=f"Corrije el gasto Prueba Edit de 5000 a 8888")
        print(f"--- ENVIANDO MENSAJE: '{request.message}' ---")
        
        response = chat_with_agent(request, bg, db, user)
        
        print(f"--- RESPUESTA DEL AGENTE ---")
        print(f"Message: {response.message}")
        print(f"Intent: {response.intent}")
        print(f"Action Taken: {response.action_taken}")

        # 3. Verificar en DB
        db.refresh(test_expense)
        print(f"\n--- VERIFICACIÓN DE BASE DE DATOS ---")
        print(f"VALOR ANTERIOR: 5000")
        print(f"VALOR ACTUAL EN DB: {test_expense.amount}")
        
        if test_expense.amount == 8888:
            print("\n✅ TEST EXITOSO: La base de datos se actualizó correctamente a 8888.")
        else:
            print(f"\n❌ TEST FALLIDO: El monto sigue siendo {test_expense.amount}")

    except Exception as e:
        print(f"❌ ERROR DURANTE EL TEST: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_edit_flow()
