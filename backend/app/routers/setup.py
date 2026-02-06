from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User
from app.deps import get_current_user

router = APIRouter(tags=["setup"])

@router.post("/initialize-user-data")
def initialize_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inicializa datos por defecto para el usuario actual:
    - Presupuesto mensual
    - Categorías con presupuesto asignado
    """
    from app.services.db_service import (
        update_monthly_budget,
        add_category_to_db,
        initialize_default_categories
    )
    from app.models.budget import Budget, Category
    
    try:
        # Verificar si ya tiene datos
        existing_budget = db.query(Budget).filter(Budget.user_id == current_user.id).first()
        existing_categories = db.query(Category).filter(Category.user_id == current_user.id).first()
        
        if existing_budget and existing_categories:
            return {
                "message": "User data already initialized",
                "status": "skipped"
            }
        
        # Configurar presupuesto mensual por defecto
        if not existing_budget:
            update_monthly_budget(db, current_user.id, 500000)  # $500,000 CLP
        
        # Inicializar categorías por defecto
        if not existing_categories:
            initialize_default_categories(db, current_user.id)
            
            # Actualizar con presupuestos reales
            categories_with_budget = [
                ("CASA", "Arriendo", 200000),
                ("CASA", "Servicios", 50000),
                ("CASA", "Supermercado", 100000),
                ("FAMILIA", "Salud", 30000),
                ("FAMILIA", "Educación", 20000),
                ("TRANSPORTE", "Bencina", 40000),
                ("TRANSPORTE", "Uber", 20000),
            ]
            
            from app.services.db_service import update_category_in_db
            for section, category, budget in categories_with_budget:
                update_category_in_db(db, current_user.id, section, category, new_budget=budget)
        
        return {
            "message": "User data initialized successfully",
            "status": "success",
            "budget": 500000,
            "categories_created": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")
