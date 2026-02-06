import os
import psycopg2
from urllib.parse import urlparse

def check_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL no encontrada en variables de entorno.")
        return

    print(f"Intentando conectar a DB...")
    # Solo mostrar parte de la URL por seguridad
    safe_url = db_url.split("@")[-1] if "@" in db_url else "..."
    print(f"URL: ...@{safe_url}")

    try:
        conn = psycopg2.connect(db_url)
        print("✅ Conexión exitosa a PostgreSQL!")
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"📊 Versión DB: {version[0]}")
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        print("\n📂 Tablas encontradas:")
        for table in tables:
            print(f" - {table[0]}")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error conectando a la BD: {e}")

if __name__ == "__main__":
    check_connection()
