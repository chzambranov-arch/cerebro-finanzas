from fastapi import APIRouter, Depends, HTTPException, Body, Header
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from app.database import get_db
from app.models.user import User
from app.models.finance import Commitment
from app.deps import get_current_user
# from app.services.sheets_service import sync_commitment_to_sheet, delete_commitment_from_sheet

router = APIRouter(tags=["commitments"])

# Config for n8n Auth
N8N_API_KEY = os.getenv("N8N_WEBHOOK_TOKEN", "lucio_secret_token_2026_change_me")

def get_user_dual_auth(
    x_n8n_api_key: Optional[str] = Header(None, alias="X-N8N-API-KEY"),
    x_n8n_token: Optional[str] = Header(None, alias="X-N8N-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Allow both N8N API Key and Standard Bearer Token.
    """
    # 1. Check n8n keys
    if (x_n8n_api_key == N8N_API_KEY) or (x_n8n_token == N8N_API_KEY):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = db.query(User).first() # Fallback
        return user

    # 2. Check Bearer Token
    if authorization:
        try:
             token = authorization.replace("Bearer ", "")
             from app.deps import get_current_user
             return get_current_user(db=db, token=token)
        except:
             pass
    
    raise HTTPException(status_code=401, detail="Authentication required (X-N8N-API-KEY or Bearer)")

# --- Pydantic Schemas ---
class CommitmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    type: str # 'DEBT', 'LOAN'
    total_amount: int
    due_date: Optional[date] = None
    status: Optional[str] = "PENDING"

class CommitmentCreate(CommitmentBase):
    pass

class CommitmentUpdate(BaseModel):
    paid_amount: Optional[int] = None
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None

class CommitmentOut(CommitmentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    paid_amount: int

    created_at: datetime

class CommitmentSummary(BaseModel):
    total_debt: float
    total_loan: float
    total_paid_debt: float
    total_paid_loan: float
    net_balance: float

# --- Endpoints ---

@router.get("/summary", response_model=CommitmentSummary)
def get_commitments_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_dual_auth)
):
    """
    Get financial summary of all commitments (Debts vs Loans).
    """
    user = current_user
    
    # Calculate DEBT (Lo que debo)
    debt_query = db.query(
        func.sum(Commitment.total_amount).label("total"),
        func.sum(Commitment.paid_amount).label("paid")
    ).filter(
        Commitment.user_id == user.id,
        Commitment.type == "DEBT"
    ).first()
    
    total_debt = debt_query.total or 0
    paid_debt = debt_query.paid or 0
    
    # Calculate LOAN (Lo que me deben / Préstamos otorgados)
    loan_query = db.query(
        func.sum(Commitment.total_amount).label("total"),
        func.sum(Commitment.paid_amount).label("paid")
    ).filter(
        Commitment.user_id == user.id,
        Commitment.type == "LOAN"
    ).first()
    
    total_loan = loan_query.total or 0
    paid_loan = loan_query.paid or 0
    
    # Balance = (Loans - Paid Loans) - (Debt - Paid Debt)
    # i.e. Assets - Liabilities
    remaining_loan = total_loan - paid_loan
    remaining_debt = total_debt - paid_debt
    
    net_balance = remaining_loan - remaining_debt
    
    return {
        "total_debt": total_debt,
        "total_loan": total_loan,
        "total_paid_debt": paid_debt,
        "total_paid_loan": paid_loan,
        "net_balance": net_balance
    }

@router.get("/", response_model=List[CommitmentOut])
def get_commitments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_dual_auth)
):
    """
    Get all commitments for the authenticated user.
    """
    user = current_user
    
    return db.query(Commitment).filter(Commitment.user_id == user.id).order_by(Commitment.status.desc(), Commitment.id.desc()).all()

@router.post("/", response_model=CommitmentOut)
def create_commitment(
    commitment: CommitmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_dual_auth)
):
    """
    Create a new commitment linked to the current user.
    """
    user = current_user

    new_commitment = Commitment(
        user_id=1,  # Forzamos usuario 1 por defecto como solicitado
        title=commitment.title,
        description=commitment.description,
        type=commitment.type,
        total_amount=commitment.total_amount,
        paid_amount=0,  # Inicializar pagado en 0
        due_date=commitment.due_date,
        status=commitment.status or "PENDING"
    )
    
    db.add(new_commitment)
    db.commit()
    db.refresh(new_commitment)

    # Sync to Sheets
    # Need to run in background or direct? Direct for MVP.
    # try:
    #     sync_commitment_to_sheet(new_commitment, user.tecnico_nombre)
    # except Exception as e:
    #     print(f"WARNING: Sync commitment failed: {e}")

    return new_commitment

@router.patch("/{commitment_id}", response_model=CommitmentOut)
def update_commitment(
    commitment_id: int,
    update_data: CommitmentUpdate,
    db: Session = Depends(get_db),
    auth: User = Depends(get_user_dual_auth) # Just for auth check
):
    """
    Update commitment (e.g., register payment).
    """
    comm = db.query(Commitment).filter(Commitment.id == commitment_id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Commitment not found")
        
    if update_data.paid_amount is not None:
        comm.paid_amount = update_data.paid_amount
    if update_data.status is not None:
        comm.status = update_data.status
    if update_data.title is not None:
        comm.title = update_data.title
    if update_data.description is not None:
        comm.description = update_data.description
    if update_data.due_date is not None:
        comm.due_date = update_data.due_date
        
    db.commit()
    db.refresh(comm)

    # Sync Update
    # Find user name?
    user_name = "Carlos" 
    user = db.query(User).filter(User.id == comm.user_id).first()
    if user: user_name = user.tecnico_nombre

    # try:
    #     sync_commitment_to_sheet(comm, user_name)
    # except Exception as e:
    #     print(f"WARNING: Sync commitment update failed: {e}")

    return comm

@router.delete("/{commitment_id}")
def delete_commitment(
    commitment_id: int,
    db: Session = Depends(get_db),
    auth: User = Depends(get_user_dual_auth) # Just for auth check
):
    """
    Delete commitment.
    """
    comm = db.query(Commitment).filter(Commitment.id == commitment_id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Commitment not found")
        
    db.delete(comm)
    db.commit()

    # Sync Delete
    # try:
    #     delete_commitment_from_sheet(commitment_id)
    # except Exception as e:
    #     print(f"WARNING: Sync commitment delete failed: {e}")

    return {"message": "Commitment deleted"}
