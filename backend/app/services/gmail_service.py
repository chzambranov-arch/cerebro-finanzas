import os.path
import base64
import re
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from app.models.finance import Expense, EmailLog
from app.services.sheets_service import sync_expense_to_sheet
from app.services.ai_service import analyze_single_email

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
    if not text: return 0
    try:
        # Quitar todo lo que no sea dígito
        clean = re.sub(r'[^\d]', '', text)
        return int(clean)
    except:
        return 0

def get_email_body(payload):
    """
    Extrae el cuerpo del mensaje de forma recursiva.
    """
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            body += get_email_body(part)
    else:
        content_type = payload.get('mimeType')
        data = payload.get('body', {}).get('data')
        if data:
            decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            if content_type == 'text/plain':
                body += decoded
            elif content_type == 'text/html':
                # Opcional: limpiar HTML con regex simple si no hay BS4
                body += re.sub(r'<[^>]+>', ' ', decoded)
    return body

def parse_bank_email(subject, snippet, sender):
    """
    Parser especializado para bancos chilenos basado en la especificación v0.2.
    """
    sender_low = sender.lower()
    snip_low = snippet.replace("\n", " ") # Normalizar para regex de una línea
    
    # 🟦 BANCO DE CHILE
    if "bancochile" in sender_low or "banco de chile" in sender_low or "serviciodetransfere" in sender_low:
        # Compra T. Crédito
        m = re.search(r'compra por\s+\$([\d\.]+).*?en\s+(.*?)\s+el\s+(\d{2}/\d{2}/\d{4})', snip_low, re.IGNORECASE)
        if m:
            return {
                "banco": "Banco de Chile", "tipo": "compra", "monto": parse_amount(m.group(1)),
                "comercio": m.group(2).strip(), "fecha": m.group(3), "medio": "tarjeta_credito"
            }
        # Transferencia a terceros (Formato multibanco/web - SUPER FLEXIBLE)
        m_amt = re.search(r'(?:Monto|monto)\s+\$?([\d\.]+)', snip_low)
        # Buscar el nombre ignorando etiquetas de campo de forma GRADY
        m_dest = re.search(r'(?:Nombre\s+y\s+Apellido|Destino|Hacia|hacia)\s+([\w\s\.\-\,]+)(?:\s+Rut|Rut|Tipo|Nº|Banco|el|fecha|$)', snip_low, re.IGNORECASE)
        
        if m_amt:
            dest = m_dest.group(1).strip() if m_dest else "Tercero"
            # Limpiar etiquetas que se hayan colado al inicio del nombre
            for label in ["Nombre y Apellido", "Destino", "Hacia"]:
                dest = re.sub("^"+label, "", dest, flags=re.IGNORECASE).strip()
            return {
                "banco": "Banco de Chile", "tipo": "transferencia", "monto": parse_amount(m_amt.group(1)),
                "destinatario": dest, "medio": "transferencia"
            }

    # 🟧 BANCOESTADO
    if "bancoestado" in sender_low:
        # Compra
        m = re.search(r'compra por\s+\$([\d\.]+)\s+en\s+(.*?)\s+asociada', snip_low, re.IGNORECASE)
        if m:
            return {
                "banco": "BancoEstado", "tipo": "compra", "monto": parse_amount(m.group(1)),
                "comercio": m.group(2).strip()
            }
        # Transferencia
        m = re.search(r'transferencia\s+desde.*?por\s+\$([\d\.]+)\s+hacia\s+(.*?)\s+el', snip_low, re.IGNORECASE)
        if m:
            return {
                "banco": "BancoEstado", "tipo": "transferencia", "monto": parse_amount(m.group(1)),
                "destinatario": m.group(2).strip()
            }

    # 🟨 SANTANDER
    if "santander" in sender_low:
        # Compra
        m = re.search(r'compra en\s+(.*?)\s+por\s+\$([\d\.]+)', snip_low, re.IGNORECASE)
        if m:
            return {
                "banco": "Santander", "tipo": "compra", "comercio": m.group(1).strip(), "monto": parse_amount(m.group(2))
            }
        # Transferencia
        m = re.search(r'transferencia por\s+\$([\d\.]+).*?a\s+(.*?)\s+el', snip_low, re.IGNORECASE)
        if m:
            return {
                "banco": "Santander", "tipo": "transferencia", "monto": parse_amount(m.group(1)), "destinatario": m.group(2).strip()
            }

    # 🟥 BCI
    if "bci" in sender_low:
        m_amt = re.search(r'Monto:\s+\$([\d\.]+)', snippet)
        m_com = re.search(r'Comercio:\s+(.*)', snippet)
        m_dest = re.search(r'Destinatario:\s+(.*)', snippet)
        if m_amt:
            res = {"banco": "BCI", "monto": parse_amount(m_amt.group(1))}
            if m_com: 
                res.update({"tipo": "compra", "comercio": m_com.group(1).strip()})
            elif m_dest:
                res.update({"tipo": "transferencia", "destinatario": m_dest.group(1).strip()})
            return res

    # 🟪 SCOTIABANK / 🟩 FALABELLA / 🟦 ITAÚ / 🟧 RIPLEY / 🟨 COOPEUCH (Lógica Genérica Mejorada)
    # Casi todos usan: "Compra por $X en Y" o "Transferencia por $X a Y"
    m_tipo = re.search(r'(compra|transferencia|pago)\s+(?:por|realizada|en|desde)?\s*\$([\d\.]+)', snip_low, re.IGNORECASE)
    if m_tipo:
        tipo = m_tipo.group(1).lower()
        monto = parse_amount(m_tipo.group(2))
        res = {"monto": monto, "tipo": tipo}
        
        # Intentar sacar banco del sender
        if "falabella" in sender_low: res["banco"] = "Banco Falabella"
        elif "itau" in sender_low: res["banco"] = "Itaú"
        elif "ripley" in sender_low: res["banco"] = "Banco Ripley"
        elif "coopeuch" in sender_low: res["banco"] = "Coopeuch"
        elif "scotiabank" in sender_low: res["banco"] = "Scotiabank"
        
        # Buscar comercio o destinatario
        m_en = re.search(r'en\s+(.*?)(?:\stel|el|con|fecha|$)', snip_low, re.IGNORECASE)
        m_a = re.search(r'(?:a|hacia)\s+(.*?)(?:\s el|el|fecha|$)', snip_low, re.IGNORECASE)
        
        if tipo == "compra" and m_en: res["comercio"] = m_en.group(1).strip()
        elif tipo == "transferencia" and m_a: res["destinatario"] = m_a.group(1).strip()
        
        return res

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

    # Search for unread emails with relevant keywords (Focus on banks)
    query = 'is:unread (subject:"compra" OR subject:"transferencia" OR subject:"notificación" OR subject:"comprobante")'
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
        
        # Normalizar para Expense model
        amount = 0
        concept = ""
        bank_name = "Banco"
        
        if data:
            amount = data.get("monto", 0)
            bank_name = data.get("banco", "Banco")
            if data.get("tipo") == "transferencia":
                concept = f"Transf a {data.get('destinatario', 'Alguien')}"
            else:
                concept = data.get("comercio", "Compra")
        
        if amount > 0:
            # Auto Categorize
            section, category = auto_categorize(concept)
            
            # Create Expense Object
            # Assuming 'section' is stored in category or logic handles it. 
            # In current model, we have `category` and `section` field? 
            # Let's check model. Usually `section` is added recently.
            
            new_expense = Expense(
                user_id=user_id,
                amount=amount,
                concept=f"{concept} ({bank_name})",
                date=date.today(),
                category=category,
                section=section,
                payment_method=bank_name,
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
            new_expenses.append(f"{concept} (${amount})")

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

def sync_emails_with_nexo(db: Session, user_id: int, limit=15):
    """
    Nexo sincroniza los correos (leídos y no leídos), los entiende y los guarda.
    """
    service = get_gmail_service()
    if not service:
        return {"status": "error", "message": "Gmail no disponible"}

    # Buscamos correos bancarios sin filtrar por unread para tener historial
    query = '(subject:"compra" OR subject:"transferencia" OR subject:"notificación" OR subject:"comprobante" OR subject:"pago")'
    results = service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
    messages = results.get('messages', [])

    new_logs = 0
    hoy = date.today()
    
    for msg in messages:
        # Evitar duplicados
        exists = db.query(EmailLog).filter(EmailLog.gmail_id == msg['id']).first()
        if exists: continue

        msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        
        # Detectar si está NO LEIDO en Gmail
        labels = msg_detail.get('labelIds', [])
        is_unread_in_gmail = 'UNREAD' in labels

        headers = msg_detail['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "Sin Asunto")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Desconocido")
        date_raw = next((h['value'] for h in headers if h['name'] == 'Date'), "")
        snippet = msg_detail.get('snippet', '')
        
        # Intentar parsear fecha real
        obj_date = hoy
        try:
            from email.utils import parsedate_to_datetime
            clean_date = re.sub(r'\(.*?\)', '', date_raw).strip()
            obj_date = parsedate_to_datetime(clean_date).date()
        except: pass

        # Obtener cuerpo completo
        full_body = get_email_body(msg_detail['payload'])
        context_for_nexo = full_body if len(full_body) > 10 else snippet
        
        # 1. Intentar Parser Determinista (Regex) - AHORRA IA
        bank_data = parse_bank_email(subject, context_for_nexo, sender)
        
        if bank_data and bank_data.get("monto"):
            category = "TRANSFERENCIA_ENVIADA" if bank_data.get("tipo") == "transferencia" else "COMPRA"
            if bank_data.get("tipo") == "transferencia":
                summary = f"Transferencia de ${bank_data['monto']:,} a {bank_data.get('destinatario', 'Tercero')}"
            else:
                summary = f"Compra de ${bank_data['monto']:,} en {bank_data.get('comercio', 'Comercio')}"
        else:
            # NO LLAMAR A IA AQUÍ para ahorrar cuota
            category = "INFO_BANCARIA"
            summary = f"{subject} ({snippet[:50]}...)"

        # Solo nos interesan como 'no procesados' si son de HOY y NO LEIDOS
        is_interesting_today = (obj_date == hoy and is_unread_in_gmail)

        # Guardamos en el historial
        log = EmailLog(
            user_id=user_id,
            gmail_id=msg['id'],
            subject=subject,
            sender=sender,
            date=obj_date,
            summary=summary,
            category=category,
            body_snippet=context_for_nexo[:1000],
            processed=not is_interesting_today # Si es hoy/unread, queda False para que Lucio pregunte
        )
        db.add(log)
        new_logs += 1

    db.commit()
    return {"status": "success", "new_emails_processed": new_logs}
