from app.database import SessionLocal
from app.models.models import User
from app.models.budget import Category, Budget
from app.models.finance import Expense, Commitment, PendingExpense, PushSubscription

db = SessionLocal()
user = db.query(User).filter(User.email=='christian.zv@cerebro.com').first()
if user:
    last_exp = db.query(Expense).filter(Expense.user_id==user.id, Expense.category=='cerveza').order_by(Expense.id.desc()).first()
    if last_exp:
        print(f"Borrando gasto incorrecto ID {last_exp.id} de ${last_exp.amount}")
        db.delete(last_exp)
        db.commit()
    
    cat = db.query(Category).filter(Category.user_id==user.id, Category.section=='ESTADIO', Category.name=='cerveza').first()
    if cat:
        old_b = cat.budget
        cat.budget += 3000
        db.commit()
        print(f"Aumentado presupuesto de 'cerveza' en ESTADIO: {old_b} -> {cat.budget}")
db.close()
