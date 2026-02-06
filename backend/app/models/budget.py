from sqlalchemy import Column, Integer, String, Date
from app.database import Base

class Budget(Base):
    """Modelo para presupuesto mensual global"""
    __tablename__ = "budgets"
    
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)  # Presupuesto mensual total
    month = Column(String, nullable=False)  # Formato: "2026-02"
    user_id = Column(Integer, nullable=False)  # Relacionado con User

class Category(Base):
    """Modelo para categorías de gastos con presupuesto asignado"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    section = Column(String, nullable=False)  # CASA, FAMILIA, etc.
    name = Column(String, nullable=False)  # Nombre de la categoría
    budget = Column(Integer, default=0)  # Presupuesto asignado a esta categoría
    user_id = Column(Integer, nullable=False)

class AppConfig(Base):
    """Configuración global de la aplicación"""
    __tablename__ = "app_config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    user_id = Column(Integer, nullable=False)
