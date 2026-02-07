import sys
import os

# Add parent directory to path to allow importing app module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.routers import finance
from app.services import sheets_service
from app.services import db_service

print("Modules imported successfully. Syntax is correct.")
