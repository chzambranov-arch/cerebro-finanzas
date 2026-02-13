"""
Servicio de base de datos para reemplazar Google Sheets
"""
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional, Dict, List
from app.models.finance import Expense
from app.models.budget import Budget, Category, AppConfig


def get_or_create_monthly_budget(db: Session, user_id: int, month: Optional[str] = None) -> int:
    """Obtiene o crea el presupuesto mensual del usuario"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    budget = db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.month == month
    ).first()
    
    if not budget:
        # Crear presupuesto inicial de $0
        budget = Budget(user_id=user_id, month=month, amount=0)
        db.add(budget)
        db.commit()
        db.refresh(budget)
    
    return budget.amount


def update_monthly_budget(db: Session, user_id: int, new_amount: int, month: Optional[str] = None) -> bool:
    """Actualiza el presupuesto mensual"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    budget = db.query(Budget).filter(
        Budget.user_id == user_id,
        Budget.month == month
    ).first()
    
    if budget:
        budget.amount = new_amount
    else:
        budget = Budget(user_id=user_id, month=month, amount=new_amount)
        db.add(budget)
    
    db.commit()
    return True


def get_categories_with_budget(db: Session, user_id: int) -> Dict[str, List[Dict]]:
    """Obtiene todas las categorías organizadas por sección con sus presupuestos"""
    categories = db.query(Category).filter(Category.user_id == user_id).all()
    
    result = {}
    for cat in categories:
        sec_name = cat.section.strip().upper()
        if sec_name not in result:
            result[sec_name] = []
        result[sec_name].append({
            "name": cat.name.strip(),
            "budget": cat.budget
        })
    
    return result


def get_dashboard_data_from_db(db: Session, user_id: int) -> Dict:
    """
    Genera los datos del dashboard desde la base de datos
    DEBE coincidir con la estructura esperada por app.js:
    - categories: Dict[section_name, {budget, spent, categories: Dict[subcat, {budget, spent}]}]
    - available_balance: int
    - monthly_budget: int
    """
    current_month = datetime.now().strftime("%Y-%m")
    
    # 1. Presupuesto mensual
    monthly_budget = get_or_create_monthly_budget(db, user_id, current_month)
    
    # 2. Gastos del mes actual
    first_day = datetime.now().replace(day=1).date()
    expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.date >= first_day
    ).all()
    
    # 3. Calcular total gastado
    total_spent = sum(exp.amount for exp in expenses)
    available_balance = monthly_budget - total_spent
    
    # 4. Obtener categorías con presupuesto
    categories_dict = get_categories_with_budget(db, user_id)
    
    # 5. Calcular gastos por categoría
    expenses_by_category = {}
    for exp in expenses:
        section = (exp.section or "OTROS").strip().upper()
        category = (exp.category or "Sin clasificar").strip()
        
        if section not in expenses_by_category:
            expenses_by_category[section] = {}
        
        if category not in expenses_by_category[section]:
            expenses_by_category[section][category] = 0
        
        expenses_by_category[section][category] += exp.amount
    
    # 6. Construir estructura compatible con frontend
    categories_output = {}
    
    # Procesar primero las secciones que tienen categorías registradas
    for section, cats in categories_dict.items():
        section_budget = 0
        section_spent = 0
        section_subcats = {}
        
        # Obtener todos los gastos de esta sección para no perder los "Sin clasificar"
        all_section_spent_data = expenses_by_category.get(section, {})
        
        # A. Procesar categorías con presupuesto
        for cat_info in cats:
            cat_name = cat_info["name"]
            if cat_name == "_TEMP_PLACEHOLDER_": continue
            
            cat_budget = cat_info["budget"]
            # Sacar el gasto de esta categoría y quitarlo de la lista temporal
            cat_spent = all_section_spent_data.pop(cat_name, 0)
            
            section_budget += cat_budget
            section_spent += cat_spent
            
            section_subcats[cat_name] = {
                "budget": cat_budget,
                "spent": cat_spent
            }
        
        # B. Si quedaron gastos en esta sección sin categoría asignada (ej: "Sin clasificar")
        for extra_cat, extra_spent in all_section_spent_data.items():
            section_spent += extra_spent
            if extra_cat in section_subcats:
                section_subcats[extra_cat]["spent"] += extra_spent
            else:
                section_subcats[extra_cat] = {
                    "budget": 0,
                    "spent": extra_spent
                }
            
        categories_output[section] = {
            "budget": section_budget,
            "spent": section_spent,
            "categories": section_subcats
        }
    
    # 7. Procesar secciones que no tienen categorías registradas pero sí gastos
    for section, extra_cats in expenses_by_category.items():
        if section not in categories_output:
            section_spent = sum(extra_cats.values())
            subcats = {name: {"budget": 0, "spent": spent} for name, spent in extra_cats.items()}
            categories_output[section] = {
                "budget": 0,
                "spent": section_spent,
                "categories": subcats
            }
    
    return {
        "monthly_budget": monthly_budget,
        "total_spent": total_spent,
        "available_balance": available_balance,
        "categories": categories_output
    }


def add_category_to_db(db: Session, user_id: int, section: str, category: str, budget: int = 0) -> bool:
    """Agrega una nueva categoría a la base de datos"""
    section = section.strip().upper()
    category = category.strip()
    
    existing = db.query(Category).filter(
        Category.user_id == user_id,
        Category.section == section,
        Category.name == category
    ).first()
    
    if existing:
        return False  # Ya existe
    
    new_cat = Category(
        user_id=user_id,
        section=section,
        name=category,
        budget=budget
    )
    db.add(new_cat)
    db.commit()
    return True


def update_category_in_db(db: Session, user_id: int, section: str, 
                          category: Optional[str] = None, 
                          new_name: Optional[str] = None, 
                          new_budget: Optional[int] = None,
                          new_section: Optional[str] = None,
                          target_type: str = "CATEGORY") -> bool:
    section = section.strip().upper()
    if category: category = category.strip()
    if new_name: new_name = new_name.strip()
    if new_section: new_section = new_section.strip().upper()

    # 1. RENOMBRAR SECCIÓN COMPLETA
    if target_type == "SECTION":
        if not new_name: return False
        
        # Buscar todas las categorías de esta sección
        cats = db.query(Category).filter(
            Category.user_id == user_id,
            Category.section == section
        ).all()
        
        if not cats: return False
        
        # Actualizar nombre de sección en Categorías
        for c in cats:
            c.section = new_name
            
        # Actualizar histórico de Gastos
        db.query(Expense).filter(
            Expense.user_id == user_id,
            Expense.section == section
        ).update({"section": new_name})
        
        db.commit()
        return True

    # 2. ACTUALIZAR SUBCATEGORÍA (Nombre, Presupuesto o Mover de Carpeta)
    else:
        if not category: return False
        
        # Buscar objeto original
        cat_obj = db.query(Category).filter(
            Category.user_id == user_id,
            Category.section.ilike(section),
            Category.name.ilike(category)
        ).first()
        
        if not cat_obj: return False
        
        # Guardar valores originales exactos para buscar en transacciones
        original_section = cat_obj.section
        original_name = cat_obj.name
        
        # A. Renombrar
        if new_name:
            cat_obj.name = new_name
            # Actualizar gastos históricos
            db.query(Expense).filter(
                Expense.user_id == user_id,
                Expense.section == original_section,
                Expense.category == original_name
            ).update({"category": new_name})
            # Actualizamos original_name para las siguientes operaciones
            original_name = new_name
            
        # B. Cambiar Presupuesto
        if new_budget is not None:
            cat_obj.budget = new_budget
            
        # C. Mover a otra Carpeta (Sección)
        if new_section:
            cat_obj.section = new_section
            # Actualizar gastos históricos
            db.query(Expense).filter(
                Expense.user_id == user_id,
                Expense.section == original_section,
                Expense.category == original_name
            ).update({"section": new_section})

        db.commit()
        return True


def delete_category_from_db(db: Session, user_id: int, section: str, category: str) -> bool:
    """Elimina una categoría de la base de datos"""
    # Verificar que no tenga gastos asociados
    has_expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.section.ilike(section),
        Expense.category.ilike(category)
    ).first()
    
    if has_expenses:
        return False
    
    cat = db.query(Category).filter(
        Category.user_id == user_id,
        Category.section.ilike(section),
        Category.name.ilike(category)
    ).first()
    
    if cat:
        db.delete(cat)
        db.commit()
        return True
    
    return False


def initialize_default_categories(db: Session, user_id: int):
    """Inicializa categorías por defecto para un nuevo usuario"""
    default_categories = [
        ("CASA", "Arriendo", 0),
        ("CASA", "Servicios", 0),
        ("CASA", "Supermercado", 0),
        ("FAMILIA", "Salud", 0),
        ("FAMILIA", "Educación", 0),
        ("TRANSPORTE", "Bencina", 0),
        ("TRANSPORTE", "Uber", 0),
        ("OTROS", "General", 0),
    ]
    
    for section, category, budget in default_categories:
        add_category_to_db(db, user_id, section, category, budget)
