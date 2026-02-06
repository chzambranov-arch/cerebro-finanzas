import os.path
import base64
import re
from typing import List, Optional
from datetime import date, datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.models.finance import Expense
from app.services.sheets_service import sync_expense_to_sheet

# If modifying these scopes, delete the file token_gmail.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

CREDENTIALS_FILE = 'gmail_credentials.json'
TOKEN_FILE = 'gmail_token.json'

def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: No se encontró {CREDENTIALS_FILE}. Descárgalo de Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

def parse_amount(text):
    # Extract number from string like "$12.990" or "CLP 5000"
    # Remove dots, keep comma if decimal? Chile uses dot for thousands.
    # regex look for $ or CLP then digits/dots
    try:
        # Simple approach: remove everything except digits
        # This assumes CLP (no cents usually). If UF/USD, logic changes.
        clean = re.sub(r'[^\d]', '', text)
        return int(clean)
    except:
        return 0

def parse_bank_email(subject, snippet, sender):
    """
    Intenta extraer datos de un correo bancario.
    Retorna dict {amount, concept, category, date} o None.
    """
    
    # --- LOGICA 1: Banco Chile / Notificaciones Compra ---
    # Subject: Notificación de Compra
    # Snippet: Compra por $4.990 en UBER EATS realizada con su Tarjeta...
    if "bancochile" in sender or "banco de chile" in sender.lower() or "notificacion" in subject.lower() or "compra con tarjeta" in subject.lower():
        # Regex flexible para Banco Chile:
        # "compra por $9.244 ... en PAYU *UBER TRIP ... el"
        # Captura 1: Monto (con puntos), Captura 2: Comercio (hasta la palabra "el" o fin de línea)
        match = re.search(r'compra por\s+\$([\d\.]+).*?\s+en\s+(.*?)\s+(?:el\s+\d{2}/\d{2}|realizada)', snippet, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            commerce = match.group(2).strip()
            
            # Limpieza extra del comercio (quitar PAYU *, etc)
            commerce = commerce.replace("PAYU *", "").replace("PAYU ", "")
            
            return {
                "amount": parse_amount(amount_str),
                "concept": commerce.title(),
                "category": "Detectar", 
                "payment_method": "Banco Chile"
            }
            
    # --- LOGICA 2: Santander ---
    # Subject: Comprobante de Compra
    if "santander" in sender.lower():
        match = re.search(r'monto de\s+\$([\d\.]+)\s+en\s+(.*)', snippet, re.IGNORECASE)
        if match:
             amount_str = match.group(1)
             commerce = match.group(2).split(" con tarjeta")[0].strip()
             return {
                "amount": parse_amount(amount_str),
                "concept": commerce.title(),
                "category": "Detectar",
                "payment_method": "Santander"
            }

    # --- LOGICA 3: Generica "Compra por $X en Y" ---
    match_gen = re.search(r'Compra por\s+\$([\d\.]+)\s+en\s+(.*)', snippet, re.IGNORECASE)
    if match_gen:
        return {
            "amount": parse_amount(match_gen.group(1)),
            "concept": match_gen.group(2).split(" ")[0].title(), # First word as concept often safe
            "category": "Otros",
            "payment_method": "Auto-Detect"
        }

    return None

def auto_categorize(concept: str):
    concept = concept.upper()
    # 1. Cargar reglas personalizadas desde Sheets
    try:
        from app.services.sheets_service import get_categorization_rules
        custom_rules = get_categorization_rules()
        
        # Buscar coincidencia exacta o parcial en reglas personalizadas
        for keyword, mapped_category in custom_rules.items():
            if keyword in concept: 
                # Si encontramos coincidencia, retornamos la categoría mapeada.
                # OJO: Necesitamos saber la SECCIÓN también. 
                # Por ahora, dejemos que la UI o un segundo paso resuelva la sección si no es obvia.
                # Pero para mantener compatibilidad, podemos inferir sección o dejarla genérica si no sabemos.
                # HACK: Si la categoría es conocida en hardcode, usaremos su sección.
                
                # Mapeo inverso rápido para secciones conocidas (Hardcode fallback)
                section = "OTROS"
                cat_upper = mapped_category.upper()
                
                # Intentar adivinar sección basada en categoría
                if any(x in cat_upper for x in ["UBER", "CABIFY", "TRANSPORTE", "ESTACIONAMIENTO"]): section = "TRANSPORTE"
                elif any(x in cat_upper for x in ["COMIDA", "RESTAURANT", "SUPERMERCADO", "JUMBO", "LIDER"]): section = "COMIDA" # OJO: Super suele ser CASA
                elif any(x in cat_upper for x in ["CASA", "HOGAR", "SUPERMERCADO"]): section = "CASA"
                elif any(x in cat_upper for x in ["NETFLIX", "SPOTIFY", "STREAMING"]): section = "VICIOS"
                elif any(x in cat_upper for x in ["SALUD", "FARMACIA", "MEDICO"]): section = "SALUD"
                
                return section, mapped_category
    except Exception as e:
        print(f"Error loading custom rules: {e}")

    # 2. Lógica Hardcoded (Fallback)
    if any(x in concept for x in ['UBER', 'CABIFY', 'METRO', 'SHELL', 'COPEC', 'BENCINA']):
        return "TRANSPORT", "Transporte"
    if any(x in concept for x in ['EATS', 'PEDIDOS', 'BURGER', 'SUSHI', 'PIZZA', 'RESTAURANT', 'STARBUCKS']):
        return "FOOD", "Comida"
    if any(x in concept for x in ['LIDER', 'JUMBO', 'UNIMARC', 'TOTTUS', 'SANTA ISABEL']):
        return "HOUSE", "Supermercado"
    if any(x in concept for x in ['NETFLIX', 'SPOTIFY', 'YOUTUBE', 'HBO', 'DISNEY']):
        return "ENTERTAINMENT", "Streaming"
    if any(x in concept for x in ['FARMACIA', 'CRUZ VERDE', 'AHUMADA', 'DOCTOR', 'CLINICA']):
        return "HEALTH", "Salud"
    return "OTROS", "General"

def process_recent_emails(db: Session, user_id: int, user_name: str, limit=10):
    service = get_gmail_service()
    if not service:
        return {"status": "error", "detail": "Gmail service not available"}

    # Search for unread emails with relevant keywords
    query = 'is:unread (subject:"compra" OR subject:"notificación de compra" OR subject:"pago realizado")'
    results = service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
    messages = results.get('messages', [])

    processed_count = 0
    new_expenses = []

    for msg in messages:
        msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        
        headers = msg_detail['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "Sin Asunto")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Desconocido")
        snippet = msg_detail.get('snippet', '')

        # Parse data
        data = parse_bank_email(subject, snippet, sender)
        
        if data and data['amount'] > 0:
            # Auto Categorize
            section, category = auto_categorize(data['concept'])
            
            # Create Expense Object
            # Assuming 'section' is stored in category or logic handles it. 
            # In current model, we have `category` and `section` field? 
            # Let's check model. Usually `section` is added recently.
            
            new_expense = Expense(
                user_id=user_id,
                amount=data['amount'],
                concept=data['concept'] + " (Auto)",
                date=date.today(),
                category=category,
                section=section,
                payment_method=data['payment_method'],
                image_url=None
            )
            
            # Inject section if model supports it (we will check if it crashes, or update model first)
            # For now, let's assume 'category' handles it or we pass it to sheet sync separately
            
            db.add(new_expense)
            db.commit()
            db.refresh(new_expense)
            
            # Sync to Sheets
            try:
                # We need to pass section to sync if possible. 
                # If sync_expense_to_sheet logic relies on expense object having .section attribute or not.
                sync_expense_to_sheet(new_expense, user_name, section=section)
            except Exception as e:
                print(f"Sync error for gmail expense: {e}")

            processed_count += 1
            new_expenses.append(f"{data['concept']} (${data['amount']})")

            # Mark as read (remove UNREAD label)
            service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
        
        else:
            # If we couldn't parse it, maybe mark as read anyway to avoid loop? 
            # Or leave it unread (better for debugging).
            pass

    return {
        "status": "success", 
        "processed": processed_count, 
        "details": new_expenses
    }
