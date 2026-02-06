"""
Script para verificar categorías en la base de datos
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.budget import Category
from app.models.finance import Expense  # Import primero
from app.models.models import User

db = SessionLocal()

try:
    # Buscar usuario Christian
    user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
    
    if not user:
        print("❌ Usuario no encontrado")
        exit(1)
    
    print(f"✅ Usuario: {user.tecnico_nombre} (ID: {user.id})")
    print("\n" + "="*60)
    print("CATEGORÍAS REGISTRADAS")
    print("="*60)
    
    # Obtener todas las categorías del usuario
    categories = db.query(Category).filter(Category.user_id == user.id).all()
    
    if not categories:
        print("\n⚠️  No hay categorías registradas")
    else:
        # Agrupar por sección
        sections = {}
        for cat in categories:
            if cat.section not in sections:
                sections[cat.section] = []
            sections[cat.section].append(cat)
        
        # Mostrar por sección
        for section, cats in sorted(sections.items()):
            print(f"\n📂 {section}")
            print("   " + "-"*50)
            total_budget = 0
            for cat in cats:
                print(f"   ├─ {cat.name}: ${cat.budget:,}")
                total_budget += cat.budget
            print(f"   └─ TOTAL: ${total_budget:,}")
        
        print("\n" + "="*60)
        print(f"Total de categorías: {len(categories)}")
        print(f"Total de secciones: {len(sections)}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
