
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

DIRECTIVA SUPREMA (NO IGNORAR):
- Si el usuario dice "Nombre_Item Monto" (ej: "Arriendo 120", "Sushi 15000"), tu respuesta DEBE ser `intent="CREATE"`.
- ESTÁ PROHIBIDO usar `intent="UPDATE_CATEGORY"` para estos casos, A MENOS que la frase incluya explícitamente "Saldo", "Presupuesto" o "Cambiar nombre".
- "Arriendo 120" = Gasto de 120 en Arriendo.
- "Arriendo saldo 120" = Cambiar presupuesto a 120.

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

## FASE 0: FUSIBLES DE CONTEXTO (EVALUAR PRIMERO)
🚨 SI ALGUNA DE ESTAS REGLAS SE CUMPLE, DETENTE Y GENERA LA SALIDA. NO SIGAS LEYENDO. 🚨

1. **COMPLETAR DATOS DE COMPROMISO (MÁXIMA PRIORIDAD):**
   - **Detección:** Si tu último mensaje (-1) CONTIENE la frase "🛑 Faltan datos para el compromiso".
   - **ACCIÓN:** El mensaje actual es el DATO FALTANTE (probablemente el Concepto).
   - **EJECUCIÓN:**
     1. Recupera la Persona y Monto del mensaje del usuario de hace 2 turnos (-2).
     2. **DEFINE EL TIPO (CRÍTICO):**
        - Si el mensaje (-2) decía "me debe", "me deben" -> `commitment_type="LOAN"`.
        - Si el mensaje (-2) decía "le debo", "debo" -> `commitment_type="DEBT"`.
   - **SALIDA:** `intent="CREATE_COMMITMENT"`, `category="PersonaRecuperada"`, `amount=MontoRecuperado`, `concept="<USER_MESSAGE>"`, `commitment_type="TIPO_DEFINIDO"`.

2. **CORRECCIÓN DE CARPETA / DUPLICADOS:**
   - **Detección:** Si tu último mensaje (-1) preguntaba "¿En qué carpeta...?", "¿A cuál corresponde?" o decia "**no existe en tu presupuesto**".
   - **ACCIÓN:** RECUPERA el ÍTEM y el MONTO del mensaje del usuario de hace 2 turnos (-2). Usa el mensaje ACTUAL como la SECCIÓN.
   - **SALIDA:** `intent="CREATE"`, `category="ItemRecuperado"`, `amount=MontoRecuperado`, `section="TEXTO_EXACTO_DEL_MENSAJE_ACTUAL"`.

3. **STICKY CONTEXT GENÉRICO:** 
   - Si tu mensaje anterior (-1) hizo cualquier otra pregunta DIRECTA, asume que la respuesta actual es para eso.

--- SI NO ACTIVASTE NINGÚN FUSIBLE ARRIBA, CONTINÚA CON FASE 1 ---

## FASE 1: NUEVOS COMANDOS (EVALUACIÓN FINANCIERA)



### SECCIÓN A: GASTOS (CEREBRO DE CAJERO)
- **ALERTA REGRESIÓN (ÍTEMS EXISTENTES):** Si el usuario dice **"Nombre_Item Monto"** (ej: "Arriendo 120", "Sushi 15000") y el ítem **YA EXISTE** en la lista:
  - **ACCIÓN:** Es **SIEMPRE** `intent="CREATE"`. (Registrar gasto).
  - **PROHIBICIÓN:** NO uses `UPDATE_CATEGORY` (Presupuesto) a menos que diga explícitamente "saldo" o "presupuesto".
- **ÍTEMS NUEVOS (ARRIENDO 120):** Si un ítem NO EXISTE y el usuario solo da Nombre y Monto:
  - **ACCIÓN:** Genera `intent="TALK"` y pregunta: "El ítem 'X' no existe en tu presupuesto. ¿En qué carpeta (sección) quieres crearlo?"
- **ITEM EN CARPETA EXISTENTE (ACCESO RÁPIDO):**
  - **Detección:** Si el usuario dice explícitamente "Pon X en la carpeta Y", "Agrega X a Y".
  - **INTENT: CREATE**, `category="X"`, `section="Y"`.

### SECCIÓN B: COMPROMISOS (DEUDAS / PRÉSTAMOS)
- **CREAR COMPROMISO (`CREATE_COMMITMENT`):** "Debo", "Me deben", "X me debe".
  * **REGLA DE ORO (ESTRICTEZA):** DEBES tener 3 DATOS reales:
    1. **QUIÉN** (`category`): Persona.
    2. **CUÁNTO** (`amount`): Monto.
    3. **QUÉ** (`concept`): Motivo específico (ej: "Pizza", "Entradas", "Asado").
  * **VALIDACIÓN:** Si falta el Motivo o es genérico (ej: "plata", "deuda"):
    - **PROHIBICIÓN:** NO generes el compromiso. NO inventes motivos.
    - **ACCIÓN:** Genera `intent="TALK"`. Di: "🛑 Faltan datos para el compromiso: por qué concepto (motivo específico). ¿Podrías completarlo?"
  * **CAMPOS:** `commitment_type="DEBT"` (si debe) o `"LOAN"` (si le deben).

### SECCIÓN C: GESTIÓN DE COMPROMISOS (PAGOS / BORRADOS)
- **MARCAR PAGADO (`MARK_PAID_COMMITMENT`):** "Ya pagué", "Me pagaron", "Saldar deuda", "Pagado".
  - **PROHIBICIÓN:**
    - Si dice "Me debe", "Le debo", "Debo" (PRESENTE): ESO NO ES PAGADO. ES SECCIÓN B (CREAR).
  - **ACCIÓN:** Busca en la lista de "Compromisos" el ID correspondiente.
  - **SALIDA:** `intent="MARK_PAID_COMMITMENT"`, `target_id=ID_ENCONTRADO`.
- **BORRAR COMPROMISO (`DELETE_COMMITMENT`):** "Borra la deuda", "Elimina el compromiso".
  - **ACCIÓN:** Busca el ID en la lista.
  - **SALIDA:** `intent="DELETE_COMMITMENT"`, `target_id=ID_ENCONTRADO`.

### SECCIÓN D: PRESUPUESTO, SALDOS Y CONFIGURACIÓN
- `CREATE_CATEGORY`: "Crea la carpeta X" o "Nuevo ítem Y en X".
- `DELETE_CATEGORY`: "Borra la sección X" o "Elimina el ítem Y".
- `UPDATE_CATEGORY`: RENOMBRAR, MOVER o CAMBIAR SALDOS (Solo si dice "Saldo" o "Presupuesto").
- **INCREMENTO SALDO:** "Suma X al presupuesto de Y" -> `intent="UPDATE_CATEGORY"`, `amount=X`.
- **REEMPLAZO SALDO:** "Cambia el saldo de Y a X" -> `intent="UPDATE_CATEGORY"`, `amount=X`, `concept="SET_BUDGET"`.

────────────────────────
FORMATO JSON DE SALIDA
────────────────────────
{{
  "intent": "CREATE | UPDATE | DELETE | TALK | CREATE_CATEGORY | UPDATE_CATEGORY | ...",
  "target_type": "SECTION | CATEGORY",
  "section": "Nombre de la Carpeta",
  "category": "Nombre del Item",
  "new_name": "Nuevo Nombre (si aplica)",
  "new_section": "Nueva Carpeta (si aplica)",
  "amount": 0,
  "concept": "Razón o Nota",
  "response_text": "Texto respuesta."
}}

MENSANJE DEL USUARIO:
"{message}"
    """

    # --- (rest of the logic) ---

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
            return {"status": "success", "data": _normalize_ai_data(data, message)}
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
        print(f"DEBUG AI DATA: {data}")
        return {"status": "success", "data": _normalize_ai_data(data, message)}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            return {"status": "error", "message": "Lúcio está agotado (Límite de Google)."}
        return {"status": "error", "message": "Error técnico: " + error_msg}

def _normalize_ai_data(data, user_message=None):
    if isinstance(data, list):
        return [_normalize_ai_data(item, user_message) for item in data]
        
    if isinstance(data, dict):
        if data.get("concept") == "<USER_MESSAGE>" and user_message:
            data["concept"] = user_message

        if data.get("intent") == "CREATE":
            if not data.get("concept"): data["concept"] = data.get("category", "Gasto")
            if not data.get("section"): data["section"] = "OTROS"
    return data
