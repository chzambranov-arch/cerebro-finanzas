
import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.budget import Category
from app.models.finance import Expense, Commitment, EmailLog
from app.models.models import User
from datetime import datetime

# Configuración de Miguel (Agente especialista en OCR y Cálculos)
MIGUEL_PROMPT = """
Eres "Miguel", el especialista técnico en OCR y análisis matemático de Cerebro Finanzas.
### TUS RESPONSABILIDADES:
1. **OCR de Precisión:** Lee cada ítem, su precio y el TOTAL final. No inventes datos.
2. **Cálculos de División:** Si Lúcio te pide 'dividir', calcula exactamente cuánto le toca a cada uno según los nombres mencionados.
3. **Sección/Carpeta:** Si el mensaje del usuario NO menciona una carpeta existente, deja la sección como null.
4. **Respuesta:** Devuelve ÚNICAMENTE un array JSON de acciones técnicas.

### FORMATO DE SALIDA (JSON):
[
  {{ "intent": "CREATE", "amount": 100, "category": "Tag", "concept": "Desc", "section": "Folder o null" }},
  {{ "intent": "CREATE_COMMITMENT", "amount": 100, "category": "Persona", "concept": "Motivo", "commitment_type": "LOAN" }}
]

Instrucción del usuario: "{user_message}"
Contexto de carpetas actuales: {sections_list}
"""

# Configuración de Faro (Agente especialista en Análisis y Patrones)
FARO_PROMPT = """
Eres "Faro", el cerebro matemático y analista de datos de Cerebro Finanzas.
Tu misión es detectar patrones, encontrar ahorros y responder preguntas complejas sobre el dinero.

### TUS RESPONSABILIDADES:
1. **Detección de Patrones:** ¿Dónde está gastando más el usuario? ¿Qué días gasta más?
2. **Resúmenes Matemáticos:** Sumas por categorías, comparativas con el presupuesto.
3. **Predicciones y Ahorro:** Basado en los gastos recientes, ¿cuánto gastará al final de mes? ¿Dónde puede recortar?
4. **Respuesta:** Devuelve un resumen técnico y analítico que Lúcio le presentará al usuario.

### CONTEXTO DISPONIBLE:
- GASTOS: {expense_context}
- CATEGORÍAS: {cat_context}
- COMPROMISOS: {comm_context}

Instrucción de Lúcio: "{user_message}"
"""

# Configuración de Nexo (Agente especialista en Correos y Memoria)
NEXO_PROMPT = """
Eres "Nexo", el enlace de comunicación y guardián de la memoria de Cerebro Finanzas.
Tu especialidad es leer correos electrónicos, entenderlos y recordar todo lo que ha llegado.

### TUS RESPONSABILIDADES:
1. **Análisis de Correos:** Identifica si un correo es una boleta, una factura, un aviso de cobro o simplemente informativo.
2. **Memoria de Nexo:** Consulta el historial de correos del usuario para responder preguntas.
3. **Resúmenes Ejecutivos:** Explica a Lúcio qué dicen los correos para que él se lo diga al usuario.
4. **Respuesta:** Devuelve un análisis detallado de los correos relevantes.

### CONTEXTO DE CORREOS (Historial de EmailLog):
{email_context}

Instrucción de Lúcio: "{user_message}"
"""

def analyze_with_nexo(user_message, email_context):
    """
    Nexo analiza el historial de correos.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return "Nexo no puede acceder a su base de datos de correos."
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = NEXO_PROMPT.format(
        user_message=user_message,
        email_context=email_context
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"ERROR NEXO: {e}")
        return "Nexo tuvo un problema revisando los correos."

def analyze_single_email(subject, sender, snippet):
    """
    Nexo analiza un correo individual para clasificarlo y resumirlo.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return {"category": "INFO", "summary": snippet[:100]}
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    Analiza este correo y devuelve un JSON con:
    - category: (GASTO, ALERTA, INFORMATIVO)
    - summary: Breve resumen de 1 frase.
    
    De: {sender}
    Asunto: {subject}
    Contenido: {snippet}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except:
        return {"category": "INFO", "summary": "Correo de " + sender}

def analyze_with_faro(user_message, expense_context, cat_context, comm_context):
    """
    Faro analiza los datos y devuelve insights.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return "Faro no tiene acceso a sus herramientas."
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = FARO_PROMPT.format(
        user_message=user_message,
        expense_context=expense_context,
        cat_context=cat_context,
        comm_context=comm_context
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"ERROR FARO: {e}")
        return "Faro tuvo un problema analizando los datos."

def analyze_with_miguel(image_data: bytes, user_message: str, sections_list: str):
    """
    Miguel analiza la boleta y devuelve la lista de acciones técnicas.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
    
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = MIGUEL_PROMPT.format(user_message=user_message, sections_list=sections_list)
    
    mime = "image/png" if image_data.startswith(b'\x89PNG') else "image/jpeg"
    content = [prompt, {'mime_type': mime, 'data': image_data}]
    
    try:
        response = model.generate_content(
            content,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"ERROR MIGUEL: {e} | Raw: {response.text if 'response' in locals() else 'No response'}")
        return None

def process_finance_message(db: Session, user_id: int, message: str, extra_context: str = None, history: list = None, image_data: bytes = None):
    """
    Lúcio es el director de orquesta. Si hay imagen, llama a Miguel.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # 1. Preparar Contexto común
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    sections = set([c.section for c in categories])
    sections_list = ", ".join(sections)
    cat_context = "\n".join([f"- [{c.section}] -> {c.name} (Presupuesto: ${c.budget:,})" for c in categories])
    
    recent_expenses = db.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.id.desc()).limit(15).all()
    expense_context = "\n".join([f" - ID: {e.id} | {e.date} | ${e.amount} | {e.concept} | [{e.section}] {e.category}" for e in recent_expenses])
    
    commitments = db.query(Commitment).filter(Commitment.user_id == user_id).order_by(Commitment.id.desc()).limit(10).all()
    comm_context = "\n".join([f" - ID: {c.id} | {'DEBO' if c.type == 'DEBT' else 'ME DEBEN'} | ${c.total_amount} | {c.title} | Estado: {c.status}" for c in commitments])

    emails = db.query(EmailLog).filter(EmailLog.user_id == user_id).order_by(EmailLog.date.desc()).limit(10).all()
    email_context = "\n".join([f" - [{e.date}] {e.sender}: {e.subject} ({e.summary})" for e in emails])

    chat_history_txt = ""
    if history:
        chat_history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])

    hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

    # CASO ESPECIAL: IMAGEN (Llamamos a Miguel)
    miguel_actions = None
    if image_data:
        print(f"[DEBUG] Llamando a Miguel para analizar boleta...")
        miguel_actions = analyze_with_miguel(image_data, message, sections_list)
    
    # CASO ESPECIAL: ANÁLISIS (Llamamos a Faro)
    faro_insights = None
    keywords_analytics = ["resumen", "patrón", "ahorro", "predicción", "análisis", "cuánto", "gasto", "total", "promedio"]
    if any(k in message.lower() for k in keywords_analytics):
        print(f"[DEBUG] Llamando a Faro para análisis de datos...")
        faro_insights = analyze_with_faro(message, expense_context, cat_context, comm_context)

    # CASO ESPECIAL: CORREOS (Llamamos a Nexo)
    nexo_insights = None
    keywords_emails = ["correo", "mail", "recibí", "llego", "gmail", "mensaje", "nexo"]
    if any(k in message.lower() for k in keywords_emails):
        print(f"[DEBUG] Llamando a Nexo para historial de correos...")
        nexo_insights = analyze_with_nexo(message, email_context)

    # Prompt de Lúcio (Orquestador y Cara del app)
    prompt = f"""
Eres "Lúcio", el asistente financiero y cara visible de Cerebro. 
Tu estilo es ejecutivo pero amigable. 

### TU EQUIPO:
1. **Miguel (Ingeniero de campo):** Lee boletas (OCR) y hace divisiones matemáticas simples.
2. **Faro (Científico de datos):** Analiza tendencias, predice gastos y busca ahorros.
3. **Nexo (Gestor de Memoria):** Administra el historial de correos y notificaciones externas.

### TU ROL:
- Eres el único que habla con el cliente.
- Coordinas a tu equipo bajo cuerda. 
- Si Faro te pasó un análisis, úsalo para responder la pregunta técnica.
- Si Miguel te pasó acciones, confírmalas.
- Si Nexo encontró información en los correos, preséntala.

### CONTEXTO DINÁMICO:
Fecha: {hoy}
SECCIONES: [{sections_list}]
HISTORIAL: {chat_history_txt}

### INFORMACIÓN DE TU EQUIPO:
- ANÁLISIS DE FARO: {faro_insights if faro_insights else "Faro no ha intervenido."}
- MEMORIA DE NEXO (EMAILS): {nexo_insights if nexo_insights else "Nexo no ha intervenido."}
- ACCIONES DE MIGUEL: {json.dumps(miguel_actions, indent=2) if miguel_actions else "Miguel no ha intervenido."}

### INSTRUCCIONES DE RESPUESTA:
- **FORMATO:** Devuelve ÚNICAMENTE un objeto JSON.
- **TONO:** Lúcio es brillante y cercano.
- **INTEGRACIÓN:** Si Faro dio un consejo de ahorro, preséntalo como algo que "tú y tu equipo de análisis" prepararon.

### JSON SCHEMA OBLIGATORIO:
{{
  "intent": "MULTI_ACTION | TALK",
  "response_text": "Tu mensaje para el usuario",
  "actions": [ ... acciones de Miguel o cualquier CREATE/COMMITMENT que Lúcio deba hacer ...]
}}

MENSAJE DEL USUARIO: "{message}"
"""
    if not gemini_key:
        return {"status": "error", "message": "No hay API Key de Gemini configurada."}

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        text_response = response.text.strip()
        
        try:
            data = json.loads(text_response)
            # Si Miguel dio acciones pero Lúcio no las incluyó explícitamente en el JSON,
            # pero sí las mencionó en el texto, las inyectamos.
            if miguel_actions and not data.get("actions"):
                data["actions"] = miguel_actions
                data["intent"] = "MULTI_ACTION"
        except Exception as e:
            # Fallback: buscar JSON con regex si falló el parseo directo
            import re
            match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except:
                    data = {"intent": "TALK", "response_text": text_response}
            else:
                data = {"intent": "TALK", "response_text": text_response}
            
        print(f"DEBUG AI DATA (LÚCIO): {data}")
        return {"status": "success", "data": _normalize_ai_data(data, message)}
    except Exception as e:
        return {"status": "error", "message": "Error técnico lúcio: " + str(e)}

def _normalize_ai_data(data, user_message=None):
    if isinstance(data, list):
        return [_normalize_ai_data(item, user_message) for item in data]
        
    if isinstance(data, dict):
        # Si tiene una lista de acciones (MULTI_ACTION), normalizar cada una
        if "actions" in data and isinstance(data["actions"], list):
             data["actions"] = [_normalize_ai_data(a, user_message) for a in data["actions"]]
             data["intent"] = "MULTI_ACTION"

        if data.get("concept") == "<USER_MESSAGE>" and user_message:
            data["concept"] = user_message

        if data.get("intent") == "CREATE":
            if not data.get("concept"): data["concept"] = data.get("category", "Gasto")
            
        # Limpieza básica de montos
        if "amount" in data and data["amount"] is not None:
            try:
                if isinstance(data["amount"], str):
                    data["amount"] = float(data["amount"].replace("$", "").replace(".", "").replace(",", ""))
            except: pass
    return data
