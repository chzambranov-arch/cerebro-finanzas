from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.finance import PendingExpense
from app.models.models import User
from app.services.notification_service import notify_user_new_expense
from pydantic import BaseModel
from datetime import date

router = APIRouter(tags=["webhooks"])

class EmailNotification(BaseModel):
    amount: int
    concept: str
    payment_method: str = "Email"
    email_id: str
    user_email: str = "christian.zv@cerebro.com" # Default for now

@router.post("/gmail-push")
def receive_gmail_notification(
    payload: EmailNotification,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Recibe una notificación push (vía Pub/Sub o post directo) de un nuevo correo.
    Guarda el gasto en la lista de pendientes para categorización manual vía Lúcio.
    """
    # 1. Buscar usuario
    user = db.query(User).filter(User.email == payload.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 2. Verificar duplicados
    exists = db.query(PendingExpense).filter(PendingExpense.raw_email_id == payload.email_id).first()
    if exists:
        return {"status": "ignored", "message": "Duplicate email ID"}

    # 3. Guardar como pendiente
    new_pending = PendingExpense(
        user_id=user.id,
        amount=payload.amount,
        concept=payload.concept,
        payment_method=payload.payment_method,
        raw_email_id=payload.email_id,
        status="PENDING"
    )
    db.add(new_pending)
    db.commit()

    # 4. Trigger Push Notification al celular (en background)
    background_tasks.add_task(notify_user_new_expense, db, user.id, payload.amount, payload.concept)

    return {"status": "success", "pending_id": new_pending.id}
