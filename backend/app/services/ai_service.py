
import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.budget import Category
from app.services.db_service import add_category_to_db
from app.services.sheets_service import add_category_to_sheet

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def process_finance_message(db: Session, user_id: int, message: str):
    """
    Procesa un mensaje de lenguaje natural usando Gemini para extraer un gasto estructurado.
    """
    if not api_key:
        return {"status": "error", "message": "No se ha configurado la API Key de Gemini"}

    # 1. Obtener contexto del usuario (Categorías existentes)
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    cat_list = [f"{c.section}/{c.name}" for c in categories]
    cat_context = ", ".join(cat_list)

    # 2. Prompt System
    prompt = f"""
    Actúa como 'Lúcio', un asistente financiero experto y amable.
    Tu objetivo es INTERPRETAR el mensaje del usuario y extraer la información para registrar un gasto.
    
    INFORMACIÓN DISPONIBLE (Categorías actuales del usuario):
    [{cat_context}]

    REGLAS DE RAZONAMIENTO:
    1. Identifica el MONTO (ej: 15000, 15k, $15.000).
    2. Identifica el CONCEPTO (ej: Sushi, Uber, Bencina).
    3. ASIGNA una CATEGORÍA y SECCIÓN basándote en la lista disponible.
    4. SI NO EXISTE una categoría exacta, busca la más lógica (ej: "Sushi" -> "Comida/Restaurante" o "Uber Eats").
       - SI y solo SI no hay nada remotamente parecido, inventa una categoría lógica nueva, pero prefiere las existentes.
    5. Detecta si menciona un método de pago (Tarjeta, Efectivo), sino asume "Débito".

    FORMATO DE RESPUESTA JSON (SIN MARKDOWN, solo JSON puro):
    {{
        "amount": 0,
        "concept": "string",
        "category": "string",
        "section": "string",
        "payment_method": "string",
        "response_text": "string (Tu respuesta amable al usuario confirmando la acción)"
    }}

    Ejemplo Usuario: "Sushi 15000"
    Respuesta JSON:
    {{
        "amount": 15000,
        "concept": "Sushi",
        "category": "Restaurante", 
        "section": "ALIMENTACION",
        "payment_method": "Débito",
        "response_text": "¡Entendido! Registré $15.000 en Sushi bajo la categoría Restaurante."
    }}

    Mensaje del Usuario: "{message}"
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        text_response = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_response)
        
        # Validar consistencia básica
        if data.get("amount", 0) <= 0:
            return {"status": "error", "message": "No pude identificar un monto válido."}

        return {"status": "success", "data": data}

    except Exception as e:
        print(f"Error Gemini: {e}")
        return {"status": "error", "message": "Lo siento, tuve un problema procesando tu solicitud."}
