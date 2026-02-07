
import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.budget import Category
from app.models.finance import Expense, Commitment
from app.models.models import User

def process_finance_message(db: Session, user_id: int, message: str, extra_context: str = None, history: list = None):
    """
    Procesa un mensaje de lenguaje natural usando OpenAI (ChatGPT) o Gemini como fallback.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # 1. Preparar Contexto común (Categorías y Gastos)
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    # Agrupamos por secciones para el contexto
    sections = set([c.section for c in categories])
    sections_list = ", ".join(sections)
    
    cat_context = "\n".join([f"- [{c.section}] -> {c.name} (Presupuesto: ${c.budget:,})" for c in categories])
    
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

    # 3. Historial de Chat
    chat_history_txt = ""
    if history:
        # Aseguramos el orden cronológico
        chat_history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])

    from datetime import datetime
    hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""
Eres "Lúcio", asistente y coach financiero personal.
Fecha actual: {hoy}

Tu rol:
- Ejecutar acciones financieras con precisión (Gastos, Categorías, Compromisos).
- Mantener la integridad de los datos.
- Desambiguar usando el historial de conversación.

────────────────────────
CONTEXTO DINÁMICO
────────────────────────

SECCIONES (CARPETAS) EXISTENTES:
[{sections_list}]

JERARQUÍA DE CATEGORÍAS (Section -> Item):
{cat_context}

GASTOS RECIENTES (ÚSALOS SOLO PARA REFERENCIA):
{expense_context}

COMPROMISOS RECIENTES:
{comm_context}

HISTORIAL RECIENTE (CRÍTICO - MEMORIA CONVERSACIONAL):
{chat_history_txt}

────────────────────────
REGLAS MAESTRAS DE EJECUCIÓN (ORDEN DE PRIORIDAD)
────────────────────────

## 1. MEMORIA Y CONTEXTO (¡PRIORIDAD MÁXIMA!)
- **REGLA DE ORO:** Antes de procesar una nueva intención, revisa si hay una PREGUNTA PENDIENTE tuya en el historial inmediato (-1).
- Si la hay, la entrada del usuario es la RESPUESTA a esa pregunta.

  **CASO DETECTADO: DESAMBIGUANDO DUPLICADOS**
  - **Detección:** Tu pregunta previa (-1) fue: "El ítem 'X' existe en varias carpetas: ... ¿A cuál corresponde?"
  - **Acción:** La respuesta actual del usuario es la SECCIÓN (Carpeta).
  - **Extracción Crítica:** Debes mirar el mensaje del usuario de hace DOS turnos (-2) para recuperar el monto, concepto e intención original (ej: "agrerga 400 a play").
  - **Resultado:** Genera `intent="CREATE"`, `amount`=monto_del_pasado, `category`="item_del_pasado", `section`=(Respuesta actual del usuario).

  **CASO DETECTADO: CREANDO NUEVA CARPETA**
  ... (Se mantiene flujo de creación de carpeta e ítem) ...

--- SI NO HAY PREGUNTA PENDIENTE, EVALÚA: ---

## 3. REGISTRO DE GASTOS (GASTO vs PRESUPUESTO)
- **EL VERBO "AGREGAR" ES SIEMPRE GASTO:** 
  * "Agrega 300", "agrerga 200", "pon 500", "suma 100", "gasto", "compré" -> **SIEMPRE son `intent="CREATE"` (GASTO NUEVO).**
  * **PROHIBICIÓN TOTAL:** NUNCA uses `intent="UPDATE_CATEGORY"` para estos verbos aunque el ítem tenga presupuesto. Cada "agrega" es un gasto que se resta del presupuesto disponible, NO una edición del presupuesto mismo.
  * **ÚNICA EXCEPCIÓN:** Solo usa `intent="UPDATE_CATEGORY"` si la frase contiene literalmente la palabra **"PRESUPUESTO"** o **"SALDO"** (ej: "Aumenta el presupuesto de X a 5000", "Cambia el saldo de Y").
- **VERIFICACIÓN DE DUPLICADOS:**
  * Si el ítem existe en >1 carpeta y el usuario no dijo cuál:
    - **INTENT: TALK**.
    - **TEXTO OBLIGATORIO:** "El ítem 'X' existe en varias carpetas: 'Carpeta1', 'Carpeta2'. ¿A cuál corresponde?"

## 4. OTRAS INTENCIONES (RESUMEN)
- `DELETE_CATEGORY`: Solo si dice "borra", "elimina" la carpeta o ítem.
- `UPDATE_CATEGORY`: Solo para RENOMBRAR, MOVER o cambiar literalmente el SALDO/PRESUPUESTO.
- `CREATE_COMMITMENT`: "Debo", "Me deben".

────────────────────────
FORMATO JSON DE SALIDA
────────────────────────
{{
  "intent": "CREATE | UPDATE | DELETE | TALK | CREATE_CATEGORY | UPDATE_CATEGORY | ...",
  "section": "Carpeta",
  "category": "Item",
  "amount": 0,
  "concept": "",
  "response_text": "Texto respuesta."
}}

MENSANJE DEL USUARIO:
"{message}"
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
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        text_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_response)
        return {"status": "success", "data": _normalize_ai_data(data)}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            return {"status": "error", "message": "Lúcio está agotado (Límite de Google)."}
        return {"status": "error", "message": "Error técnico: " + error_msg}

def _normalize_ai_data(data):
    if isinstance(data, list):
        return [_normalize_ai_data(item) for item in data]
        
    if isinstance(data, dict):
        if data.get("intent") == "CREATE":
            if not data.get("concept"): data["concept"] = data.get("category", "Gasto")
            if not data.get("section"): data["section"] = "OTROS"
        elif data.get("intent") == "CREATE_COMMITMENT":
            # Asegurar que el concepto capture la nota mini del usuario
            if not data.get("concept") and data.get("category"):
                data["concept"] = data["category"]
    return data
