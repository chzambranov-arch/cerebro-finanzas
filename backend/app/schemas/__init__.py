from __future__ import annotations
from pydantic import BaseModel
import datetime
from typing import List, Optional
from enum import Enum

class ExpenseType(str, Enum):
    FIJO = "FIJO"
    CON_SALDO = "CON_SALDO"
    ESPORADICO = "ESPORADICO"

# --- ITEM SCHEMAS ---
class ItemBase(BaseModel):
    name: str
    budget: int
    type: ExpenseType

class ItemCreate(ItemBase):
    folder_id: int

class Item(ItemBase):
    id: int
    folder_id: int
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# --- FOLDER SCHEMAS ---
class FolderBase(BaseModel):
    name: str
    initial_balance: int

class FolderCreate(FolderBase):
    pass

class Folder(FolderBase):
    id: int
    user_id: int
    created_at: datetime.datetime
    items: List[Item] = []
    
    class Config:
        from_attributes = True

# --- EXPENSE SCHEMAS ---
class ExpenseBase(BaseModel):
    description: str
    amount: int
    date: datetime.date
    folder_id: int
    item_id: Optional[int] = None
    item: Optional[int] = None
    type: ExpenseType

class ExpenseCreate(ExpenseBase):
    user_id: Optional[int] = None
    # Make date optional in create
    date: Optional[datetime.date] = None

class Expense(ExpenseBase):
    id: int
    user_id: int
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# --- DASHBOARD / SUMMARY SCHEMAS ---
class FolderSummary(BaseModel):
    id: int
    name: str
    initial_balance: int
    spent: int
    remaining: int

class DashboardData(BaseModel):
    user_name: str
    total_budget: int
    total_spent: int
    total_remaining: int
    folders: List[FolderSummary]

# --- USER SCHEMAS ---
class UserResponse(BaseModel):
    id: int
    email: str
    tecnico_nombre: str
    is_active: bool
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
