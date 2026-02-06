
import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.budget import Category
from app.models.finance import Expense
from app.models.models import User

def process_finance_message(db: Session, user_id: int, message: str):
    """
    Procesa un mensaje de lenguaje natural usando OpenAI (ChatGPT) o Gemini como fallback.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # 1. Preparar Contexto común
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    # Presentar de forma clara: Sección -> Categoría
    cat_context = "\n".join([f"- [{c.section}] -> {c.name}" for c in categories])
    
    recent_expenses = db.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.id.desc()).limit(15).all()
    expense_context_list = []
    for e in recent_expenses:
        expense_context_list.append(f" - ID: {e.id} | {e.date} | ${e.amount} | {e.concept} | [{e.section}] {e.category}")
    expense_context = "\n".join(expense_context_list)

    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""
    Eres 'Lúcio', asitente de finanzas. 
    Fecha actual: {hoy}

    GASTOS RECIENTES:
    {expense_context}

    JERARQUÍA DE CATEGORÍAS (Usa exactamente estos nombres):
    {cat_context}

    REGLAS DE ORO:
    - SIEMPRE usa 'CREATE' para mensajes como "Agrega X", "Gasto X en Y", o simplemente "X en Y".
    - NUNCA sumes montos. Si el usuario dice "Agrega 2000", el amount es 2000. Punto.
    - 'target_id' (CRÍTICO para UPDATE/DELETE):
        * Si dice "el último", usa el ID del primer gasto de la lista de 'GASTOS RECIENTES'.
        * Si menciona un concepto o monto, busca el ID que mejor coincida en esa lista.
        * SIEMPRE debe ser el ID numérico.
    - 'section': Nombre sin corchetes (ej: 'CASA').
    - 'category': Nombre sin flechas (ej: 'Arriendo').
    - 'UPDATE' solo si dice explícitamente "Corrije", "Edita" o "Cambia" (ej: "no eran 1500, eran 2000").

    JSON FORMAT:
    {{
        "intent": "CREATE | UPDATE | DELETE | TALK",
        "target_id": ID_O_NUMERICO,
        "amount": monto_final_sin_sumar_nada,
        "concept": "Nombre limpio",
        "category": "Nombre_exacto_limpio",
        "section": "Seccion_exacta_limpio",
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
