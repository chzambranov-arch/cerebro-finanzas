"""
Script para inicializar datos de prueba en la base de datos
"""
from app.database import SessionLocal
from app.models.models import User
from app.services.db_service import update_monthly_budget, add_category_to_db

db = SessionLocal()

try:
    # Obtener el usuario Christian
    user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
    
    if not user:
        print("❌ Usuario no encontrado")
        exit(1)
    
    print(f"✅ Usuario encontrado: {user.email} (ID: {user.id})")
    
    # Configurar presupuesto mensual
    print("\n📊 Configurando presupuesto mensual...")
    update_monthly_budget(db, user.id, 500000)  # $500,000 CLP
    print("✅ Presupuesto configurado: $500,000")
    
    # Agregar categorías
    print("\n📂 Agregando categorías...")
    categories = [
        ("CASA", "Arriendo", 200000),
        ("CASA", "Servicios", 50000),
        ("CASA", "Supermercado", 100000),
        ("FAMILIA", "Salud", 30000),
        ("FAMILIA", "Educación", 20000),
        ("TRANSPORTE", "Bencina", 40000),
        ("TRANSPORTE", "Uber", 20000),
        ("COMIDA", "Restaurantes", 30000),
        ("OTROS", "General", 10000),
    ]
    
    for section, category, budget in categories:
        result = add_category_to_db(db, user.id, section, category, budget)
        if result:
            print(f"  ✅ {section} / {category}: ${budget:,}")
        else:
            print(f"  ⚠️  {section} / {category} ya existe")
    
    print("\n✨ Datos de prueba inicializados correctamente!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
