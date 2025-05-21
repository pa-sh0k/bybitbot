from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum

# Enums
class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalCategory(str, Enum):
    SPOT = "SPOT"
    LINEAR = "LINEAR"
    INVERSE = "INVERSE"

class SignalAction(str, Enum):
    OPEN = "OPEN"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    CLOSE = "CLOSE"
    INCREASE = "INCREASE"

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    SIGNAL_PURCHASE = "signal_purchase"
    SIGNAL_USED = "signal_used"

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

# User schemas
class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    balance: int
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Signal schemas
class SignalBase(BaseModel):
    symbol: str
    category: SignalCategory
    signal_type: SignalType
    action: SignalAction
    position_size: str
    leverage: int = 1

class SignalCreate(SignalBase):
    entry_price: Optional[float] = None
    entry_time: datetime

class SignalUpdate(BaseModel):
    action: SignalAction
    position_size: str
    old_position_size: Optional[str] = None
    exit_price: Optional[str] = None
    exit_time: Optional[datetime] = None
    close_percentage: Optional[float] = None
    realized_pnl: Optional[str] = None
    profit_percentage: Optional[float] = None

class Signal(SignalBase):
    id: int
    signal_number: int
    old_position_size: Optional[str] = None
    entry_price: Optional[str] = None
    exit_price: Optional[str] = None
    close_percentage: Optional[float] = None
    realized_pnl: Optional[str] = None
    unrealized_pnl: Optional[str] = None
    profit_percentage: Optional[float] = None
    entry_time: datetime
    exit_time: Optional[datetime] = None
    is_completed: bool
    created_at: datetime

    class Config:
        orm_mode = True

# Position update schemas
class PositionUpdateCreate(BaseModel):
    signal_id: int
    action: SignalAction
    position_size: str
    price: Optional[str] = None
    close_percentage: Optional[float] = None
    realized_pnl: Optional[str] = None

class PositionUpdate(BaseModel):
    id: int
    signal_id: int
    action: SignalAction
    position_size: str
    price: Optional[str] = None
    close_percentage: Optional[float] = None
    realized_pnl: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True

# Transaction schemas
class TransactionBase(BaseModel):
    user_id: int
    amount: float
    transaction_type: TransactionType
    details: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Package schemas
class PackageBase(BaseModel):
    name: str
    signals_count: int
    price: float

class PackageCreate(PackageBase):
    pass

class Package(PackageBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Webhook schemas
class BybitWebhookEntry(BaseModel):
    symbol: str
    side: str  # Buy or Sell
    price: float
    quantity: float
    leverage: float
    timestamp: datetime
    order_id: str
    position_idx: int  # 0: one-way, 1: Buy side, 2: Sell side

class BybitWebhookExit(BaseModel):
    symbol: str
    side: str  # Buy or Sell (opposite of entry)
    price: float
    quantity: float
    timestamp: datetime
    order_id: str
    position_idx: int
    profit_percentage: float

# Summary schemas
class DailySummary(BaseModel):
    date: datetime
    signals: List[Signal]
    total_profit: float