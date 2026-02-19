from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Boolean, Enum as SqEnum
from sqlalchemy.orm import relationship
from datetime import datetime, date
import enum
from app.database import Base

class ExpenseType(str, enum.Enum):
    FIJO = "FIJO"
    CON_SALDO = "CON_SALDO"
    ESPORADICO = "ESPORADICO"

class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    initial_balance = Column(Integer, default=0) # Asignado manualmente
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User")
    items = relationship("Item", back_populates="folder", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="folder", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"))
    name = Column(String, nullable=False)
    budget = Column(Integer, default=0) # Monto asignado (Fijo o Saldo)
    type = Column(SqEnum(ExpenseType), nullable=False) # FIJO o CON_SALDO (Esporádicos don't have items)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    folder = relationship("Folder", back_populates="items")
    expenses = relationship("Expense", back_populates="item")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    folder_id = Column(Integer, ForeignKey("folders.id"))
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True) # Null for Esporádico
    amount = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    date = Column(Date, default=date.today)
    type = Column(SqEnum(ExpenseType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    folder = relationship("Folder", back_populates="expenses")
    item = relationship("Item", back_populates="expenses")

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False) # "user" or "assistant"
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Commitment(Base):
    __tablename__ = "commitments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(String, nullable=False) # 'DEBT', 'LOAN'
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0)
    due_date = Column(Date, nullable=True)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

