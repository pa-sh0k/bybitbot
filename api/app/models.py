from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class SignalType(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalCategory(enum.Enum):
    SPOT = "SPOT"
    LINEAR = "LINEAR"  # USDT perpetual
    INVERSE = "INVERSE"  # Inverse perpetual


class SignalAction(enum.Enum):
    OPEN = "OPEN"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    CLOSE = "CLOSE"
    INCREASE = "INCREASE"


class UserRole(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class TransactionType(enum.Enum):
    DEPOSIT = "DEPOSIT"
    SIGNAL_PURCHASE = "SIGNAL_PURCHASE"
    SIGNAL_USED = "SIGNAL_USED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    balance = Column(Integer, default=0)  # Number of signals available
    balance_usdt = Column(Integer, default=0)  # Number of USDT on the balance
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="user")
    received_signals = relationship("UserSignal", back_populates="user")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    signal_number = Column(Integer, index=True)  # Sequential ID for user display
    symbol = Column(String, index=True)  # e.g. BTC/USDT
    category = Column(Enum(SignalCategory))  # spot, linear, inverse
    signal_type = Column(Enum(SignalType))  # BUY or SELL
    action = Column(Enum(SignalAction))  # open, partial_close, close, increase

    # Position details
    position_size = Column(String)  # Use string to store exact decimal values
    old_position_size = Column(String, nullable=True)  # For partial closes
    entry_price = Column(String, nullable=True)
    exit_price = Column(String, nullable=True)
    leverage = Column(String, default="1")  # Only for futures

    # Performance tracking
    close_percentage = Column(Float, nullable=True)  # % of position closed
    realized_pnl = Column(String, nullable=True)  # Realized profit/loss
    unrealized_pnl = Column(String, nullable=True)  # Unrealized profit/loss
    profit_percentage = Column(Float, nullable=True)  # % profit/loss

    # Timestamps
    entry_time = Column(DateTime(timezone=True))
    exit_time = Column(DateTime(timezone=True), nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    received_by_users = relationship("UserSignal", back_populates="signal")
    position_updates = relationship("PositionUpdate", back_populates="signal")


class UserSignal(Base):
    __tablename__ = "user_signals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    signal_id = Column(Integer, ForeignKey("signals.id"))
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="received_signals")
    signal = relationship("Signal", back_populates="received_by_users")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)  # USDT amount or signals count
    transaction_type = Column(Enum(TransactionType))
    details = Column(Text, nullable=True)  # Additional info
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    signals_count = Column(Integer)
    price = Column(Float)  # in USDT
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PositionUpdate(Base):
    __tablename__ = "position_updates"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("signals.id"))

    # Update details
    action = Column(Enum(SignalAction))
    position_size = Column(String)
    price = Column(String, nullable=True)
    close_percentage = Column(Float, nullable=True)
    realized_pnl = Column(String, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    signal = relationship("Signal", back_populates="position_updates")