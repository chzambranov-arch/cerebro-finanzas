from sqlalchemy import Column, Integer, String, Boolean, Enum as SqEnum
from app.database import Base
import enum

class Role(str, enum.Enum):
    TECH = "TECH"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    tecnico_nombre = Column(String, nullable=False, unique=True) # Used as display name
    role = Column(SqEnum(Role), default=Role.TECH)
    is_active = Column(Boolean, default=True)
