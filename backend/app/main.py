from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Load env vars before anything else
load_dotenv()

from app.core.config import settings
from app.database import engine, Base, SessionLocal
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.models.user import User, Role
from app.routers import auth, users, finance, lucio_hybrid, commitments
from app.models.finance import Folder, Item, Expense, ChatHistory
from app.core.security import get_password_hash

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.on_event("startup")
def init_data():
    db = SessionLocal()
    try:
        print("Initializing system data...")
        # Add/Update test user
        user = db.query(User).filter(User.email == "christian.zv@cerebro.com").first()
        if not user:
            print("Creating user christian.zv@cerebro.com...")
            user = User(
                email="christian.zv@cerebro.com",
                hashed_password=get_password_hash("cerebro_pass"),
                tecnico_nombre="Christian ZV",
                is_active=True,
                role=Role.TECH
            )
            db.add(user)
        else:
            print("Updating password for christian.zv@cerebro.com...")
            user.hashed_password = get_password_hash("cerebro_pass")
            user.is_active = True
        db.commit()
    except Exception as e:
        print(f"Error initializing user: {e}")
    finally:
        db.close()
    
    print("--- LÚCIO v3.0 ENGINE READY ---")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Static Files (Frontend) using absolute path to be safe
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(finance.router, prefix=f"{settings.API_V1_STR}/expenses", tags=["finance"])

# NEW: Architectural v4.0 routes
app.include_router(finance.router, prefix="/api/v3/finance", tags=["finance_v3"])
app.include_router(lucio_hybrid.router)  # /api/v3/lucio
app.include_router(commitments.router, prefix="/api/v3/commitments", tags=["commitments"])

@app.get("/debug-deploy")
def debug_deploy():
    return {
        "version": "v3.0.0-ManualFolders",
        "cwd": os.getcwd(),
        "files_in_static": os.listdir(static_dir) if os.path.exists(static_dir) else "not found",
        "env_check": "LOCAL",
        "database": "SQLite"
    }

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/index.html")
def read_index_html():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/manifest.json")
def get_manifest():
    return FileResponse(os.path.join(static_dir, "manifest.json"))

@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(static_dir, "sw.js"))

@app.get("/icon-512.png")
def get_icon():
    return FileResponse(os.path.join(static_dir, "icon-512.png"))
