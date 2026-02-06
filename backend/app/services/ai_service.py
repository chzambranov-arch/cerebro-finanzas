
import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.budget import Category
from app.models.finance import Expense, Commitment
from app.models.models import User

def process_finance_message(db: Session, user_id: int, message: str):
    """
    Procesa un mensaje de lenguaje natural usando OpenAI (ChatGPT) o Gemini como fallback.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # 1. Preparar Contexto común (Categorías y Gastos)
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    cat_context = "\n".join([f"- [{c.section}] -> {c.name}" for c in categories])
    
    recent_expenses = db.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.id.desc()).limit(15).all()
    expense_context_list = [f" - ID: {e.id} | {e.date} | ${e.amount} | {e.concept} | [{e.section}] {e.category}" for e in recent_expenses]
    expense_context = "\n".join(expense_context_list)
    
    # 2. Compromisos (Debo / Me Deben)
    commitments = db.query(Commitment).filter(Commitment.user_id == user_id).order_by(Commitment.id.desc()).limit(10).all()
    comm_context_list = []
    for c in commitments:
        c_type = "DEBO" if c.type == 'DEBT' else "ME DEBEN"
        comm_context_list.append(f" - ID: {c.id} | {c_type} | ${c.total_amount} | {c.title} | Estado: {c.status}")
    comm_context = "\n".join(comm_context_list)

    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""
    Eres 'Lúcio', asitente de finanzas. 
    Fecha actual: {hoy}

    GASTOS RECIENTES:
    {expense_context}

    COMPROMISOS (DEUDAS/PRÉSTAMOS):
    {comm_context}

    JERARQUÍA DE CATEGORÍAS (Usa exactamente estos nombres):
    {cat_context}

    REGLAS DE ORO:
    - SIEMPRE usa 'CREATE' para gastos normales.
    - USA 'CREATE_COMMITMENT' si el usuario dice "Debo X a...", "X me debe...", "Le presté X a...".
    - USA 'MARK_PAID_COMMITMENT' si el usuario dice "Ya pagué X", "Me pagaron lo de Y", "Marca como pagado el compromiso Z". (Esto no lo borra, solo le pone el ticket verde).
    - USA 'DELETE_COMMITMENT' solo si el usuario pide explícitamente BORRAR o ELIMINAR el registro.
    - 'target_id': ID numérico para UPDATE/DELETE (Gasto) o DELETE_COMMITMENT/MARK_PAID_COMMITMENT (Compromiso).
    - 'commitment_type': 'DEBT' (si yo debo) o 'LOAN' (si me deben).
    - NUNCA sumes montos.
    - 'section'/'category': Solo para gastos (CREATE).
    - 'UPDATE' solo si pide explícitamente corregir un gasto existente.

    JSON FORMAT:
    {{
    "intent": "CREATE | UPDATE | DELETE | CREATE_COMMITMENT | MARK_PAID_COMMITMENT | DELETE_COMMITMENT | TALK",
        "target_id": ID_O_NUMERICO,
        "amount": monto_final,
        "concept": "Referencia o Nombre Persona",
        "category": "Nombre_exacto (solo gastos)",
        "section": "Seccion_exacta (solo gastos)",
        "commitment_type": "DEBT | LOAN",
        "payment_method": "metodo",
        "response_text": "Respuesta corta"
    }}

    PROCESA ESTE MENSAJE: "{message}"
    """

    # --- INTENTAR OPENAI PRIMERO SI HAY KEY ---
    if openai_key and len(openai_key) > 10:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Eres Lúcio, experto financiero."}, {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(response.choices[0].message.content)
            return {"status": "success", "data": _normalize_ai_data(data)}
        except Exception as e:
            print(f"OpenAI Error: {e}")

    # --- FALLBACK A GEMINI ---
    if not gemini_key:
        return {"status": "error", "message": "No hay API Keys configuradas (Gemini/OpenAI)"}

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-1.5-flash') # Formato correcto sin models/
        response = model.generate_content(prompt)
        text_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_response)
        return {"status": "success", "data": _normalize_ai_data(data)}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            return {"status": "error", "message": "Lúcio está agotado (Límite de Google). Por favor, configura tu OPENAI_API_KEY para evitar esto."}
        return {"status": "error", "message": "Error técnico: " + error_msg}

def _normalize_ai_data(data: dict):
    if data.get("intent") == "CREATE":
        if not data.get("concept"): data["concept"] = data.get("category", "Gasto")
        if not data.get("section"): data["section"] = "OTROS"
        if not data.get("payment_method"): data["payment_method"] = "Débito"
    return data
