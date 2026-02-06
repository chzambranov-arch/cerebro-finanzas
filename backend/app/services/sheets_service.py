import gspread
from oauth2client.service_account import ServiceAccountCredentials
from app.core.config import settings
from datetime import date
import json

def get_sheet():
    try:
        creds_json = settings.GOOGLE_SHEETS_CREDENTIALS_JSON
        if not creds_json:
            import os
            creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
            
        if not creds_json:
            print("ERROR [SHEETS] No se encontraron credenciales en GOOGLE_SHEETS_CREDENTIALS_JSON")
            return None
        
        creds_json = creds_json.strip()
        if creds_json.startswith("'") or creds_json.startswith('"'):
            creds_json = creds_json[1:-1]
        
        # Try Base64 decoding (Robust way for Cloud Env)
        import base64
        import binascii
        try:
            # Check if it looks like base64 (no { at start)
            if not creds_json.strip().startswith('{'):
                decoded = base64.b64decode(creds_json).decode('utf-8')
                if decoded.strip().startswith('{'):
                    creds_json = decoded
                    print("DEBUG [SHEETS] Base64 credentials detected and decoded.")
        except Exception:
            pass # Not base64, continue normal flow
        
        creds_dict = json.loads(creds_json)
        
        # FIX: Handle escaped newlines in private_key (common in Railway/Heroku)
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(settings.GOOGLE_SHEET_ID)
    except Exception as e:
        print(f"ERROR [SHEETS] Falló la autenticación: {e}")
        return None

def normalize_sheet_date(date_val):
    if not date_val: return ""
    s = str(date_val).strip()
    try:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = date.fromisoformat(s) if fmt=="%Y-%m-%d" else datetime.strptime(s, fmt).date()
                return dt.strftime("%Y-%m-%d")
            except: continue
        return s
    except: return s

def normalize_amount(amt_val):
    if amt_val is None: return "0"
    s = str(amt_val).strip()
    for char in ["$", ".", ","]:
        s = s.replace(char, "")
    return s



def sync_expense_to_sheet(expense, tech_name, section=None):
    """Appends an expense row to the 'Gastos' sheet."""
    # Support both SQLAlchemy objects and dictionaries (for background tasks)
    is_dict = isinstance(expense, dict)
    concept = expense["concept"] if is_dict else expense.concept
    
    print(f"\n>>> [SHEETS START] Syncing expense {concept}...")
    try:
        sheet = get_sheet()
        if not sheet: return

        try:
            ws = sheet.worksheet("Gastos")
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title="Gastos", rows=1000, cols=8)
            ws.append_row(["Fecha", "Concepto", "Sección", "Categoría", "Monto", "Método Pago", "Usuario", "Imagen URL"])

        new_row = [
            str(expense["date"]) if is_dict else str(expense.date),
            concept,
            section or "OTROS",
            expense["category"] if is_dict else expense.category,
            expense["amount"] if is_dict else expense.amount,
            (expense["payment_method"] or "N/A") if is_dict else (expense.payment_method or "N/A"),
            tech_name,
            (expense["image_url"] or "") if is_dict else (expense.image_url or "")
        ]
        ws.append_row(new_row)
        print(f"DEBUG [SHEETS] Expense appended to 'Gastos'.")
    except Exception as e:
        print(f"ERROR [SHEETS] Expense sync failed: {e}")

def get_dashboard_data(tech_name: str):
    """
    Retrieves balance, budget, and category spending from 'Config', 'Presupuesto' and 'Gastos' sheets.
    """
    try:
        sheet = get_sheet()
        if not sheet: return None

        # 1. Get Config (Name, Global Budget)
        config = {"name": tech_name if tech_name else "Usuario", "monthly_budget": 0}
        try:
            ws_config = sheet.worksheet("Config")
            data = ws_config.get_all_records()
            for row in data:
                key = str(row.get("Key", "")).lower()
                # Only overwrite name if tech_name wasn't provided (fallback)
                if ("nombre" in key or "name" in key) and not tech_name: 
                    config["name"] = row.get("Value", "Carlos")
                if "presupuesto" in key or "budget" in key: config["monthly_budget"] = int(row.get("Value", 0))
        except: pass

        # 2. Get Budgets per Section (Hierarchical)
        sections = {}
        # category_to_section is useful for mapping expenses that only have category
        category_to_section = {}
        try:
            ws_budget = sheet.worksheet("Presupuesto")
            data = ws_budget.get_all_records()
            for row in data:
                sec = str(row.get("Sección") or "OTROS").strip()
                cat = str(row.get("Categoría") or row.get("Category") or "General").strip()
                bud = int(row.get("Presupuesto") or row.get("Budget") or 0)
                
                category_to_section[cat] = sec
                
                if sec not in sections:
                    sections[sec] = {"budget": 0, "spent": 0, "categories": {}}
                
                sections[sec]["budget"] += bud
                sections[sec]["categories"][cat] = {"budget": bud, "spent": 0}
        except: pass

        # 3. Calculate Spent per Category/Section (current month)
        try:
            ws_gastos = sheet.worksheet("Gastos")
            data = ws_gastos.get_all_records()
            from datetime import date
            current_month = date.today().month
            current_year = date.today().year
            
            total_spent = 0
            for row in data:
                try:
                    fecha_str = str(row.get("Fecha", ""))
                    from datetime import datetime
                    d = None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try: d = datetime.strptime(fecha_str, fmt); break
                        except: continue
                    
                    if d and d.month == current_month and d.year == current_year:
                        sec = str(row.get("Sección", "")).strip()
                        cat = str(row.get("Categoría") or row.get("Category", "")).strip()
                        monto = int(row.get("Monto") or row.get("Amount") or 0)
                        
                        total_spent += monto
                        
                        # Use section from row if available, else map from category
                        if not sec and cat in category_to_section:
                            sec = category_to_section[cat]
                        
                        if not sec: sec = "OTROS"
                        
                        if sec not in sections:
                            sections[sec] = {"budget": 0, "spent": 0, "categories": {}}
                        
                        sections[sec]["spent"] += monto
                        if cat:
                            if cat not in sections[sec]["categories"]:
                                sections[sec]["categories"][cat] = {"budget": 0, "spent": 0}
                            sections[sec]["categories"][cat]["spent"] += monto
                except: continue
        except: pass

        return {
            "user_name": config["name"],
            "available_balance": config["monthly_budget"] - total_spent,
            "monthly_budget": config["monthly_budget"],
            "categories": sections, # Frontend will now receive sections as the top-level
            "total_spent": total_spent
        }
    except Exception as e:
        print(f"ERROR [SHEETS] get_dashboard_data failed: {e}")
        return None




def add_category_to_sheet(section: str, category: str, budget: int = 0):
    """
    Adds a new category (subcategory) to the 'Presupuesto' sheet.
    """
    print(f"DEBUG [SHEETS] Adding category '{category}' to section '{section}'")
    try:
        sheet = get_sheet()
        if not sheet: return False
        
        try:
            ws = sheet.worksheet("Presupuesto")
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title="Presupuesto", rows=100, cols=3)
            ws.append_row(["Sección", "Categoría", "Presupuesto"])

        # Check for duplicates?
        # Ideally yes, but for MVP let's just append.
        # Structure: Sección, Categoría, Presupuesto
        ws.append_row([section, category, budget])
        return True
    except Exception as e:
        print(f"ERROR [SHEETS] Add category failed: {e}")
        return False

def delete_category_from_sheet(section: str, category: str):
    """
    Deletes a category from the 'Presupuesto' sheet.
    """
    print(f"DEBUG [SHEETS] Deleting category '{category}' from section '{section}'")
    try:
        sheet = get_sheet()
        if not sheet: 
            print("ERROR [SHEETS] No sheet access")
            return False
        
        try:
            ws = sheet.worksheet("Presupuesto")
        except Exception as e:
            print(f"ERROR [SHEETS] Worksheet 'Presupuesto' not found: {e}")
            return False

        all_rows = ws.get_all_values()
        if not all_rows: return False
        
        headers = [h.strip().lower() for h in all_rows[0]]
        try:
            sec_col = -1
            cat_col = -1
            for c in ["sección", "seccion", "section"]:
                if c in headers: sec_col = headers.index(c); break
                
            for c in ["categoría", "categoria", "category"]:
                if c in headers: cat_col = headers.index(c); break
                
            if sec_col == -1 or cat_col == -1:
                print(f"ERROR [SHEETS] Cols not found: sec={sec_col}, cat={cat_col}")
                return False
                
            target_sec = section.strip().lower()
            target_cat = category.strip().lower()

            # Find row to delete
            for i, row in enumerate(all_rows[1:], start=2):
                if len(row) > max(sec_col, cat_col):
                    r_sec = row[sec_col].strip().lower()
                    r_cat = row[cat_col].strip().lower()
                    if r_sec == target_sec and r_cat == target_cat:
                        ws.delete_rows(i)
                        print(f"DEBUG [SHEETS] Deleted row {i}: {section}/{category}")
                        return True
            
            print(f"DEBUG [SHEETS] No match found for '{target_sec}' / '{target_cat}'")
            return False # Not found
            
        except Exception as e:
            print(f"ERROR [SHEETS] Delete finding row failed: {e}")
            return False

    except Exception as e:
        print(f"ERROR [SHEETS] Delete category failed: {e}")
        return False

def update_category_in_sheet(section: str, category: str, new_budget: int, new_cat: str = None):
    """
    Updates a category's budget in the 'Presupuesto' sheet and optionally renames it.
    """
    print(f"\n[SHEETS] >>> START update_category_in_sheet")
    print(f"[SHEETS] Target: {section} / {category} -> Budget: {new_budget}, New Name: {new_cat}")
    try:
        sheet = get_sheet()
        if not sheet: 
            print("[SHEETS] ERROR: Could not get sheet access.")
            return False
        
        ws = sheet.worksheet("Presupuesto")
        all_rows = ws.get_all_values()
        if not all_rows: 
            print("[SHEETS] ERROR: 'Presupuesto' sheet is empty.")
            return False
        
        headers = [h.strip().lower() for h in all_rows[0]]
        print(f"[SHEETS] Headers found: {headers}")
        
        sec_col = -1
        cat_col = -1
        bud_col = -1
        
        for c in ["sección", "seccion", "section"]:
            if c in headers: sec_col = headers.index(c); break
        for c in ["categoría", "categoria", "category"]:
            if c in headers: cat_col = headers.index(c); break
        for c in ["presupuesto", "budget"]:
            if c in headers: bud_col = headers.index(c); break
            
        if sec_col == -1 or cat_col == -1 or bud_col == -1:
            print(f"[SHEETS] ERROR: Missing columns (Sec:{sec_col}, Cat:{cat_col}, Bud:{bud_col})")
            return False
            
        target_sec = section.strip().lower()
        target_cat = category.strip().lower()
        found = False

        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) > max(sec_col, cat_col):
                r_sec = row[sec_col].strip().lower()
                r_cat = row[cat_col].strip().lower()
                
                if r_sec == target_sec and r_cat == target_cat:
                    print(f"[SHEETS] MATCH FOUND at row {i}")
                    found = True
                    
                    # 1. Update Budget (Column is 1-based, so bud_col + 1)
                    ws.update_cell(i, bud_col + 1, new_budget)
                    print(f"[SHEETS] Budget updated to {new_budget}")
                    
                    # 2. Update Name if requested and different
                    clean_new = str(new_cat).strip() if new_cat else None
                    if clean_new and clean_new.lower() != target_cat:
                         print(f"[SHEETS] RENAMING: '{category}' -> '{clean_new}'")
                         ws.update_cell(i, cat_col + 1, clean_new)
                         print(f"[SHEETS] Name updated in PresupuestoSheet")
                         
                         # 3. Propagate to Expenses (Historical)
                         try:
                             rename_category_in_expenses_sheet(sheet, section, category, clean_new)
                         except Exception as e:
                             print(f"[SHEETS] WARNING: Historical rename failed: {e}")
                             # We still return True because the primary budget/name was updated
                    break
        
        if not found:
            print(f"[SHEETS] WARNING: No match found for {target_sec}/{target_cat}")
            return False
            
        print("[SHEETS] update_category_in_sheet COMPLETED SUCCESSFULLY")
        return True
    except Exception as e:
        print(f"[SHEETS] CRITICAL ERROR in update_category_in_sheet: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"ERROR [SHEETS] Update category failed: {e}")
        return False

def sync_commitment_to_sheet(commitment, user_name="Carlos"):
    """
    Syncs a commitment to 'Compromisos' sheet (Append or Update).
    """
    print(f"DEBUG [SHEETS] Syncing commitment {commitment.id} - {commitment.title}")
    try:
        sheet = get_sheet()
        if not sheet: return

        try:
            ws = sheet.worksheet("Compromisos")
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title="Compromisos", rows=1000, cols=9)
            ws.append_row(["ID", "Fecha Creación", "Título", "Tipo", "Monto Total", "Monto Pagado", "Vencimiento", "Estado", "Usuario"])

        # Prepare row data
        # ID, Created, Title, Type, Total, Paid, Due, Status, User
        row_data = [
            str(commitment.id),
            str(commitment.created_at.date()) if commitment.created_at else "",
            commitment.title,
            commitment.type, # DEBT / LOAN
            commitment.total_amount,
            commitment.paid_amount,
            str(commitment.due_date) if commitment.due_date else "",
            commitment.status,
            user_name
        ]

        # Find if ID exists (Column 1)
        found_cell = None
        try:
            found_cell = ws.find(str(commitment.id), in_column=1)
        except:
            pass

        if found_cell:
            # Update existing row
            # gspread's update method: ws.update(range_name, values=List[List])
            # Row index is found_cell.row
            # We want to update columns A to I (1 to 9)
            cell_range = f"A{found_cell.row}:I{found_cell.row}"
            ws.update(cell_range, [row_data])
            print(f"DEBUG [SHEETS] Updated existing commitment row {found_cell.row}")
        else:
            # Append
            ws.append_row(row_data)
            print(f"DEBUG [SHEETS] Appended new commitment.")

    except Exception as e:
        print(f"ERROR [SHEETS] Commitment sync failed: {e}")

def delete_commitment_from_sheet(commitment_id: int):
    """
    Deletes a commitment row from sheet by ID.
    """
    print(f"DEBUG [SHEETS] Deleting commitment {commitment_id}")
    try:
        sheet = get_sheet()
        if not sheet: return

        try:
            ws = sheet.worksheet("Compromisos")
        except:
            return

        try:
            found_cell = ws.find(str(commitment_id), in_column=1)
            if found_cell:
                ws.delete_rows(found_cell.row)
                print(f"DEBUG [SHEETS] Deleted commitment row {found_cell.row}")
        except:
            print("DEBUG [SHEETS] Commitment ID not found for deletion.")
            pass

    except Exception as e:
        print(f"ERROR [SHEETS] Delete commitment failed: {e}")

def delete_expense_from_sheet(expense_data: dict, tech_name: str):
    """
    Attempts to find and delete a matching expense row in the 'Gastos' sheet.
    Since we don't have unique IDs in Sheets for expenses yet, we match by multiple fields.
    """
    print(f"DEBUG [SHEETS] Syncing DELETION for expense: {expense_data.get('concept')} (${expense_data.get('amount')})")
    try:
        sheet = get_sheet()
        if not sheet: return
        try:
            ws = sheet.worksheet("Gastos")
        except:
            return

        all_values = ws.get_all_values()
        if not all_values: return

        target_date = normalize_sheet_date(expense_data.get("date"))
        target_concept = str(expense_data.get("concept")).strip().lower()
        target_amount = normalize_amount(expense_data.get("amount"))
        target_user = str(tech_name).strip().lower()

        found_row = -1
        for i in range(len(all_values) - 1, 0, -1):
            row = all_values[i]
            if len(row) >= 7:
                r_date = normalize_sheet_date(row[0])
                r_concept = str(row[1]).strip().lower()
                r_amount = normalize_amount(row[4])
                r_user = str(row[6]).strip().lower()

                if (r_date == target_date and 
                    r_concept == target_concept and 
                    r_amount == target_amount and 
                    r_user == target_user):
                    found_row = i + 1
                    break
        
        if found_row != -1:
            ws.delete_rows(found_row)
            print(f"DEBUG [SHEETS] Deleted expense row {found_row} from Sheets.")
        else:
            print("DEBUG [SHEETS] No matching expense found in Sheets for deletion.")

    except Exception as e:
        print(f"ERROR [SHEETS] Delete expense from sheet failed: {e}")

def update_monthly_budget(new_budget: int):
    """
    Updates the 'Presupuesto Mensual' (or similar key) in the 'Config' sheet.
    """
    print(f"DEBUG [SHEETS] Updating Monthly Budget to {new_budget}")
    try:
        sheet = get_sheet()
        if not sheet: return False

        try:
            ws = sheet.worksheet("Config")
        except gspread.WorksheetNotFound:
            print("ERROR [SHEETS] 'Config' sheet not found.")
            return False

        # Find the row with Key like 'Presupuesto'
        cell = ws.find("Presupuesto")
        if not cell:
            cell = ws.find("Budget")
        
        if cell:
            # Assuming Value is in Column B (col 2), and Key is Column A (col 1)
            # If find returned a cell in Col A, we update Col B in the same row.
            ws.update_cell(cell.row, cell.col + 1, new_budget)
            print(f"DEBUG [SHEETS] Budget updated in row {cell.row}")
            return True
        else:
            print("ERROR [SHEETS] Key 'Presupuesto' not found in Config.")
            return False

    except Exception as e:
        print(f"ERROR [SHEETS] Update budget failed: {e}")
        return False

def get_categorization_rules():
    """
    Fetches custom categorization rules from 'Reglas' sheet.
    Returns a dict: {"UBER EATS": "Uber Eats", "RAPPI": "Uber Eats", ...}
    """
    try:
        sheet = get_sheet()
        if not sheet: return {}
        
        try:
            ws = sheet.worksheet("Reglas")
        except:
            return {} # Sheet doesn't exist yet

        rows = ws.get_all_values()
        if not rows: return {}
        
        # Assume Header: Keyword | Category
        # Skip header
        rules = {}
        for row in rows[1:]:
            if len(row) >= 2:
                keyword = row[0].strip().upper()
                category = row[1].strip()
                if keyword and category:
                    rules[keyword] = category
        return rules
    except Exception as e:
        print(f"ERROR [SHEETS] Failed to fetch rules: {e}")
        return {}

def get_all_expenses_from_sheet():
    """
    Fetches all expenses from the 'Gastos' sheet to populate the local DB.
    """
    print("DEBUG [SHEETS] Fetching ALL expenses from Sheets...")
    try:
        sheet = get_sheet()
        if not sheet: return []
        
        try:
            ws = sheet.worksheet("Gastos")
        except:
            return []

        all_rows = ws.get_all_values()
        if not all_rows: return []
        
        headers = [h.strip().lower() for h in all_rows[0]]
        
        # Mappings
        try:
            col_date = headers.index("fecha")
            col_concept = headers.index("concepto")
            col_category = -1
            if "categoría" in headers: col_category = headers.index("categoría")
            if "categoria" in headers: col_category = headers.index("categoria")
            if "category" in headers: col_category = headers.index("category")
            
            col_section = -1
            if "sección" in headers: col_section = headers.index("sección")
            if "seccion" in headers: col_section = headers.index("seccion")
            
            col_amount = -1
            if "monto" in headers: col_amount = headers.index("monto")
            if "amount" in headers: col_amount = headers.index("amount")
            
            col_method = -1
            if "método pago" in headers: col_method = headers.index("método pago")
            if "payment" in headers: col_method = headers.index("payment")
            
            col_img = -1
            if "imagen url" in headers: col_img = headers.index("imagen url")
        except ValueError:
            return []

        expenses = []
        for row in all_rows[1:]:
            try:
                # Basic validation
                if len(row) <= col_amount: continue
                
                fecha_str = row[col_date]
                monto_str = row[col_amount]
                if not fecha_str or not monto_str: continue

                # Parse Date
                final_date = None
                from datetime import datetime
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try: 
                        final_date = datetime.strptime(fecha_str, fmt).date()
                        break
                    except: continue
                
                if not final_date: continue

                # Parse Amount (remove $ and points)
                clean_monto = monto_str.replace("$", "").replace(".", "").replace(",", "")
                # Assuming CLP (no decimals usually, but if comma decimal exists)
                # If 12.000 -> 12000. If 12,000 -> 12000? Chile uses dot for thousands.
                final_amount = int(clean_monto)

                expenses.append({
                    "date": final_date,
                    "concept": row[col_concept],
                    "category": row[col_category] if col_category != -1 else "General",
                    "section": row[col_section] if col_section != -1 else "OTROS",
                    "amount": final_amount,
                    "payment_method": row[col_method] if col_method != -1 else "N/A",
                    "image_url": row[col_img] if col_img != -1 and len(row) > col_img else None
                })
            except Exception as e:
                # print(f"Skipping row error: {e}")
                continue
                
        return expenses

    except Exception as e:
        print(f"ERROR [SHEETS] Get all expenses failed: {e}")
        return []
def rename_category_in_expenses_sheet(sheet, section, old_cat, new_cat):
    """
    Finds all expenses in 'Gastos' sheet matching old_cat and section, and updates them to new_cat.
    """
    print(f"[SHEETS] >>> START rename_category_in_expenses_sheet")
    try:
        ws = sheet.worksheet("Gastos")
        all_rows = ws.get_all_values()
        if not all_rows: return
        
        headers = [h.strip().lower() for h in all_rows[0]]
        sec_col = -1
        cat_col = -1
        for c in ["sección", "seccion", "section"]:
            if c in headers: sec_col = headers.index(c); break
        for c in ["categoría", "categoria", "category"]:
            if c in headers: cat_col = headers.index(c); break
            
        if cat_col == -1: 
            print("[SHEETS] ERROR: 'Categoría' column not found in Gastos.")
            return

        target_sec = section.strip().lower()
        target_cat = old_cat.strip().lower()
        
        cells_to_update = []
        # Import Cell here just in case, but using fully qualified if possible
        import gspread.cell
        
        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) > cat_col:
                r_sec = row[sec_col].strip().lower() if sec_col != -1 else ""
                r_cat = row[cat_col].strip().lower()
                
                if (sec_col == -1 or r_sec == target_sec) and r_cat == target_cat:
                    cells_to_update.append(gspread.cell.Cell(row=i, col=cat_col + 1, value=new_cat))
        
        if cells_to_update:
            print(f"[SHEETS] Updating {len(cells_to_update)} records in 'Gastos'...")
            ws.update_cells(cells_to_update)
            print("[SHEETS] Historical propagation DONE.")
        else:
            print("[SHEETS] No historical records found to update.")
            
    except Exception as e:
        print(f"[SHEETS] ERROR in rename_category_in_expenses_sheet: {e}")
        import traceback
        traceback.print_exc()

def update_expense_in_sheet(old_data: dict, new_data: dict, tech_name: str):
    """
    Finds an expense by old_data and updates it with new_data.
    """
    print(f"DEBUG [SHEETS] Syncing UPDATE for expense: {old_data.get('concept')} -> {new_data.get('concept')}")
    try:
        sheet = get_sheet()
        if not sheet: return False
        try:
            ws = sheet.worksheet("Gastos")
        except:
            return False

        all_values = ws.get_all_values()
        if not all_values: return False

        # Match criteria
        target_date = normalize_sheet_date(old_data.get("date"))
        target_concept = str(old_data.get("concept")).strip().lower()
        target_amount = normalize_amount(old_data.get("amount"))
        target_user = str(tech_name).strip().lower()

        found_row = -1
        for i in range(len(all_values) - 1, 0, -1):
            row = all_values[i]
            if len(row) >= 7:
                r_date = normalize_sheet_date(row[0])
                r_concept = str(row[1]).strip().lower()
                r_amount = normalize_amount(row[4])
                r_user = str(row[6]).strip().lower()

                if (r_date == target_date and 
                    r_concept == target_concept and 
                    r_amount == target_amount and 
                    r_user == target_user):
                    found_row = i + 1
                    break
        
        if found_row != -1:
            # Prepare new row
            new_row = [
                str(new_data.get("date")),
                new_data.get("concept"),
                new_data.get("section", "OTROS"),
                new_data.get("category"),
                new_data.get("amount"),
                new_data.get("payment_method") or "N/A",
                tech_name,
                new_data.get("image_url") or ""
            ]
            cell_range = f"A{found_row}:H{found_row}"
            ws.update(cell_range, [new_row])
            print(f"DEBUG [SHEETS] Updated expense row {found_row} in Sheets.")
            return True
        else:
            print("DEBUG [SHEETS] No matching expense found in Sheets for update.")
            return False

    except Exception as e:
        print(f"ERROR [SHEETS] Update expense in sheet failed: {e}")
        return False
