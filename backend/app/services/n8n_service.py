
"""
Servicio para comunicación con n8n y gestión directa de BD
"""
import httpx
import os
from typing import Dict, Any
from app.schemas.n8n_schemas import GastoRequestN8N, GastoResponseN8N

# Configuración
N8N_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/lucio-gastos")
N8N_TOKEN = os.getenv("N8N_WEBHOOK_TOKEN", "")


class N8NService:
    """
    Servicio para enviar requests a n8n y procesar responses.
    También maneja la creación directa de Folders e Items usando los modelos correctos.
    """
    
    @staticmethod
    async def ejecutar_accion_n8n(action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        NUEVO: Ejecutor unificado de acciones desde n8n.
        
        n8n enviará un JSON con la decisión de la IA:
        {
            "intent": "CREATE_EXPENSE",
            "user_id": 1,
            "data": {...},
            "needs_folder_creation": false,
            "needs_item_creation": true
        }
        
        Este método ejecuta la acción en orden:
        1. Crear carpeta si es necesario
        2. Crear item si es necesario
        3. Registrar gasto
        """
        from app.database import SessionLocal
        from app.models.finance import Folder, Item, Expense, ExpenseType
        from datetime import date
        
        db = SessionLocal()
        try:
            intent = action_data.get("intent")
            
            # Robust conversion for user_id
            user_id_raw = action_data.get("user_id")
            if user_id_raw is None:
                return {"status": "error", "reply": "Falta user_id en el payload"}
            user_id = int(user_id_raw)
            
            data = action_data.get("data", {})
            
            # Paso 1: Crear carpeta si es necesario
            if action_data.get("needs_folder_creation"):
                folder_name = data.get("carpeta")
                existing_folder = db.query(Folder).filter(
                    Folder.user_id == user_id,
                    Folder.name == folder_name
                ).first()
                
                if not existing_folder:
                    new_folder = Folder(
                        user_id=user_id,
                        name=folder_name,
                        initial_balance=data.get("saldo_inicial", 0)
                    )
                    db.add(new_folder)
                    db.commit()
                    db.refresh(new_folder)
            
            # Paso 2: Crear item si es necesario
            if action_data.get("needs_item_creation"):
                folder_name = data.get("carpeta")
                item_name = data.get("item")
                
                folder_obj = db.query(Folder).filter(
                    Folder.user_id == user_id,
                    Folder.name == folder_name
                ).first()
                
                if not folder_obj:
                    return {
                        "status": "ERROR",
                        "reply": f"La carpeta '{folder_name}' no existe. Creala primero."
                    }
                
                existing_item = db.query(Item).filter(
                    Item.folder_id == folder_obj.id,
                    Item.name == item_name
                ).first()
                
                if not existing_item:
                    tipo_enum = ExpenseType.CON_SALDO
                    if data.get("tipo_gasto") == "FIJO":
                        tipo_enum = ExpenseType.FIJO
                    
                    new_item = Item(
                        folder_id=folder_obj.id,
                        name=item_name,
                        type=tipo_enum,
                        budget=data.get("presupuesto", 0)
                    )
                    db.add(new_item)
                    db.commit()
                    db.refresh(new_item)
            
            # Paso 3: Ejecutar accion principal
            if intent == "CREATE_EXPENSE":
                return await N8NService._crear_gasto_directo(db, user_id, data)
            
            elif intent == "CREATE_FOLDER":
                return {
                    "status": "success",
                    "reply": f"Carpeta '{data.get('nombre')}' creada exitosamente.",
                    "action_taken": True
                }
            
            elif intent == "CREATE_ITEM":
                return {
                    "status": "success",
                    "reply": f"Item '{data.get('nombre')}' creado en '{data.get('carpeta')}'.",
                    "action_taken": True
                }
            
            else:
                return {
                    "status": "error",
                    "reply": f"Intent desconocido: {intent}"
                }
                
        except Exception as e:
            db.rollback()
            return {
                "status": "error",
                "reply": f"Error ejecutando accion: {str(e)}"
            }
        finally:
            db.close()
    
    @staticmethod
    async def _crear_gasto_directo(db, user_id: int, data: Dict) -> Dict[str, Any]:
        """
        Crea el gasto directamente en la DB (sin pasar por n8n otra vez).
        """
        from app.models.finance import Folder, Item, Expense, ExpenseType
        from datetime import date
        
        # Buscar carpeta
        folder_obj = db.query(Folder).filter(
            Folder.user_id == user_id,
            Folder.name == data.get("carpeta")
        ).first()
        
        if not folder_obj:
            return {
                "status": "error",
                "reply": f"Carpeta '{data.get('carpeta')}' no encontrada."
            }
        
        # Buscar item (si aplica)
        item_obj = None
        item_val = data.get("item")
        
        if item_val is not None:
            # Si traemos un valor, intentamos identificar el item
            try:
                # Si es un ID numérico (enviado como string o int)
                item_id_int = int(item_val)
                item_obj = db.query(Item).filter(
                    Item.id == item_id_int,
                    Item.folder_id == folder_obj.id
                ).first()
            except (ValueError, TypeError):
                # Si no es numérico, buscamos por nombre
                item_obj = db.query(Item).filter(
                    Item.folder_id == folder_obj.id,
                    Item.name == str(item_val)
                ).first()
        else:
            # Si item es None, se procesa como gasto ESPORÁDICO
            print("Registrando gasto esporádico sin vínculo a ítem.")
        
        # Mapear tipo
        tipo_enum = ExpenseType.ESPORADICO
        if data.get("tipo_gasto") == "FIJO":
            tipo_enum = ExpenseType.FIJO
        elif data.get("tipo_gasto") == "CON_SALDO":
            tipo_enum = ExpenseType.CON_SALDO
        
        # Crear gasto
        nuevo_gasto = Expense(
            user_id=user_id,
            folder_id=folder_obj.id,
            item_id=item_obj.id if item_obj else None,
            amount=int(data.get("monto", 0)),
            description=data.get("descripcion") or f"Gasto en {folder_obj.name}",  # Prioridad: 'descripcion'
            date=date.today(),
            type=tipo_enum
        )
        
        # EL SALDO SE CALCULA DINAMICAMENTE EN LA APP (NO RESTAR AQUI)
        # db.refresh(nuevo_gasto) -> Esto es suficiente
        
        db.add(nuevo_gasto)
        db.commit()
        db.refresh(nuevo_gasto)
        
        return {
            "status": "success",
            "reply": f"Registre ${data.get('monto'):,} en {folder_obj.name}",
            "action_taken": True,
            "gasto_id": nuevo_gasto.id
        }
    
    @staticmethod
    async def registrar_gasto(gasto_data: GastoRequestN8N) -> GastoResponseN8N:
        """
        Envía un gasto a n8n para procesamiento
        """
        headers = {
            "Authorization": f"Bearer {N8N_TOKEN}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    N8N_URL,
                    json=gasto_data.dict(),
                    headers=headers
                )
                response.raise_for_status()
                
                # Parsear y validar respuesta
                response_data = response.json()
                return GastoResponseN8N(**response_data)
                
            except httpx.HTTPStatusError as e:
                print(f"❌ Error HTTP de n8n: {e.response.status_code}")
                print(f"Response: {e.response.text}")
                return GastoResponseN8N(
                    status="ERROR",
                    mensaje=f"Error en n8n: {e.response.status_code}",
                    alertas=[]
                )
                
            except httpx.RequestError as e:
                print(f"❌ Error de conexión con n8n: {str(e)}")
                return GastoResponseN8N(
                    status="ERROR",
                    mensaje="No se pudo conectar con n8n. Verifica que esté corriendo.",
                    alertas=[]
                )
    
    @staticmethod
    async def crear_carpeta(user_id: Any, nombre_carpeta: str, saldo_inicial: float = 0.0) -> Dict[str, Any]:
        """
        Crea una carpeta (Folder) directamente en la DB.
        """
        from app.database import SessionLocal
        from app.models.finance import Folder
        
        db = SessionLocal()
        try:
            # Cast user_id to int to match DB schema
            uid = int(user_id)
            
            # Verificar si ya existe
            existing = db.query(Folder).filter(
                Folder.user_id == uid,
                Folder.name == nombre_carpeta
            ).first()
            
            if existing:
                return {
                    "status": "ERROR",
                    "mensaje": f"La carpeta '{nombre_carpeta}' ya existe"
                }
            
            # Crear carpeta
            nueva_carpeta = Folder(
                user_id=uid,
                name=nombre_carpeta,
                initial_balance=int(saldo_inicial) 
            )
            
            db.add(nueva_carpeta)
            db.commit()
            db.refresh(nueva_carpeta)
            
            return {
                "status": "OK",
                "mensaje": f"Carpeta '{nombre_carpeta}' creada exitosamente",
                "carpeta": {
                    "id": nueva_carpeta.id,
                    "nombre": nueva_carpeta.name,
                    "saldo_inicial": nueva_carpeta.initial_balance
                }
            }
            
        except Exception as e:
            db.rollback()
            return {
                "status": "ERROR",
                "mensaje": f"Error al crear carpeta: {str(e)}"
            }
        finally:
            db.close()
    
    @staticmethod
    async def crear_item(
        user_id: Any,
        carpeta: str,
        nombre_item: str,
        tipo_item: str,
        saldo_item: float = None,
        monto_fijo: float = None,
        fecha_pago: str = None
    ) -> Dict[str, Any]:
        """
        Crea un item directamente en la DB.
        """
        from app.database import SessionLocal
        from app.models.finance import Item, Folder, ExpenseType
        
        db = SessionLocal()
        try:
            uid = int(user_id)
            
            # 1. Buscar la carpeta (Folder) por nombre
            folder_obj = db.query(Folder).filter(
                Folder.user_id == uid,
                Folder.name == carpeta
            ).first()
            
            if not folder_obj:
                return {
                    "status": "ERROR",
                    "mensaje": f"La carpeta '{carpeta}' no existe. Créala primero."
                }
            
            # 2. Verificar si item ya existe en esa carpeta
            existing = db.query(Item).filter(
                Item.folder_id == folder_obj.id,
                Item.name == nombre_item
            ).first()
            
            if existing:
                return {
                    "status": "ERROR",
                    "mensaje": f"El item '{nombre_item}' ya existe en '{carpeta}'"
                }
            
            # 3. Mapear tipo_item (String) a Enum (ExpenseType)
            tipo_enum = ExpenseType.ESPORADICO
            if tipo_item == "FIJO":
                tipo_enum = ExpenseType.FIJO
            elif tipo_item == "CON_SALDO":
                tipo_enum = ExpenseType.CON_SALDO
            
            # 4. Crear item
            budget_val = 0
            if saldo_item is not None:
                budget_val = int(saldo_item)
            elif monto_fijo is not None:
                budget_val = int(monto_fijo)
                
            nuevo_item = Item(
                folder_id=folder_obj.id,
                name=nombre_item,
                type=tipo_enum,
                budget=budget_val
            )
            
            db.add(nuevo_item)
            db.commit()
            db.refresh(nuevo_item)
            
            return {
                "status": "OK",
                "mensaje": f"Item '{nombre_item}' creado exitosamente en '{carpeta}'",
                "item": {
                    "id": nuevo_item.id,
                    "nombre": nuevo_item.name,
                    "tipo": nuevo_item.type.value if hasattr(nuevo_item.type, "value") else str(nuevo_item.type),
                    "presupuesto": nuevo_item.budget
                }
            }
            
        except Exception as e:
            print(f"Error detallado crear_item: {e}")
            db.rollback()
            return {
                "status": "ERROR",
                "mensaje": f"Error al crear item: {str(e)}"
            }
        finally:
            db.close()
