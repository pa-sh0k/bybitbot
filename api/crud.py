from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import models, schemas


# User operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_telegram_id(db: Session, telegram_id: int):
    return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def get_users_with_signals_balance(db: Session, min_balance: int = 1):
    """Get users with signals balance >= min_balance"""
    return db.query(models.User).filter(
        models.User.is_active == True,
        models.User.signals_balance >= min_balance
    ).all()


def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        usdt_balance=0.0,
        signals_balance=0
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def check_transaction_exists(db: Session, transaction_id: str) -> bool:
    """Check if a transaction with the given ID already exists in details field"""
    return db.query(models.Transaction).filter(
        models.Transaction.details.contains(f"transaction_id:{transaction_id}")
    ).first() is not None


def update_usdt_balance(db: Session, user_id: int, amount: float, transaction_id: str):
    """Update user's USDT balance"""
    db_user = get_user(db, user_id)

    if transaction_id and check_transaction_exists(db, transaction_id):
        # Transaction already processed, return existing user data without changes
        db_user = get_user(db, user_id)
        return {
            "success": True,
            "duplicate": True,
            "message": "Transaction already processed",
            "user": db_user
        }

    transaction = schemas.TransactionCreate(
            user_id=db_user.id,
            amount=amount,
            transaction_type=schemas.TransactionType.DEPOSIT,
            details=f"USDT balance deposit | transaction_id:{transaction_id}"
        )
    create_transaction(db, transaction)

    if db_user:
        db_user.usdt_balance += amount
        db.commit()
        db.refresh(db_user)

    return {
        "success": True,
        "duplicate": False,
        "message": "Balance updated successfully",
        "user": db_user
    }


def update_signals_balance(db: Session, user_id: int, amount: int):
    """Update user's signals balance"""
    db_user = get_user(db, user_id)
    if db_user:
        db_user.signals_balance += amount
        db.commit()
        db.refresh(db_user)
    return db_user


def purchase_signals_with_usdt(db: Session, user_id: int, package_id: int):
    """Purchase signals using USDT balance"""
    db_user = get_user(db, user_id)
    if not db_user:
        return {"success": False, "error": "User not found"}

    db_package = get_package(db, package_id)
    if not db_package:
        return {"success": False, "error": "Package not found"}

    if db_user.usdt_balance < db_package.price:
        return {"success": False, "error": "Insufficient USDT balance"}

    # Deduct USDT and add signals
    db_user.usdt_balance -= db_package.price
    db_user.signals_balance += db_package.signals_count

    db.commit()
    db.refresh(db_user)

    # Record transaction
    transaction = schemas.TransactionCreate(
        user_id=user_id,
        amount=db_package.price,
        transaction_type=schemas.TransactionType.SIGNAL_PURCHASE,
        details=f"Purchased {db_package.signals_count} signals for {db_package.price} USDT"
    )
    create_transaction(db, transaction)

    return {
        "success": True,
        "usdt_balance": db_user.usdt_balance,
        "signals_balance": db_user.signals_balance,
        "package": db_package.name,
        "signals_added": db_package.signals_count
    }


# Signal operations
def get_signal(db: Session, signal_id: int):
    return db.query(models.Signal).filter(models.Signal.id == signal_id).first()


def get_signals(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Signal).order_by(models.Signal.created_at.desc()).offset(skip).limit(limit).all()


def get_open_signals(db: Session):
    return db.query(models.Signal).filter(models.Signal.is_completed == False).all()


def get_signals_by_date(db: Session, date_obj: date):
    return db.query(models.Signal).filter(
        func.date(models.Signal.exit_time) == date_obj,
        models.Signal.is_completed == True
    ).all()


def create_signal(db: Session, signal: schemas.SignalCreate):
    # Get the next signal number
    max_number = db.query(func.max(models.Signal.signal_number)).scalar() or 0
    next_number = max_number + 1

    # Create signal instance with all required fields
    db_signal = models.Signal(
        signal_number=next_number,
        symbol=signal.symbol,
        category=signal.category,
        signal_type=signal.signal_type,
        action=signal.action,  # FIX: Add the missing action field
        position_size=signal.position_size,
        leverage=signal.leverage,
        entry_price=signal.entry_price,
        entry_time=signal.entry_time,
        is_completed=False
    )
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


def update_signal(db: Session, signal_id: int, signal_update: schemas.SignalUpdate):
    db_signal = get_signal(db, signal_id)
    if db_signal:
        db_signal.action = signal_update.action
        db_signal.position_size = signal_update.position_size

        if signal_update.entry_price:
            db_signal.entry_price = signal_update.entry_price
        if signal_update.old_position_size:
            db_signal.old_position_size = signal_update.old_position_size
        if signal_update.exit_price:
            db_signal.exit_price = signal_update.exit_price
        if signal_update.exit_time:
            db_signal.exit_time = signal_update.exit_time
        if signal_update.close_percentage is not None:
            db_signal.close_percentage = signal_update.close_percentage
        if signal_update.realized_pnl:
            db_signal.realized_pnl = signal_update.realized_pnl
        if signal_update.profit_percentage is not None:
            db_signal.profit_percentage = signal_update.profit_percentage

        db.commit()
        db.refresh(db_signal)
    return db_signal


def mark_signal_completed(db: Session, signal_id: int):
    db_signal = get_signal(db, signal_id)
    if db_signal:
        db_signal.is_completed = True
        db.commit()
        db.refresh(db_signal)
    return db_signal


# Position update operations
def create_position_update(db: Session, update: schemas.PositionUpdateCreate):
    try:
        db_update = models.PositionUpdate(
            signal_id=update.signal_id,
            action=update.action,
            position_size=update.position_size,
            price=update.price,
            close_percentage=update.close_percentage,
            realized_pnl=update.realized_pnl
        )
        db.add(db_update)
        db.commit()
        db.refresh(db_update)
        return db_update
    except Exception as e:
        db.rollback()
        # Check if the PositionUpdate model exists
        if "models" in str(e) and "PositionUpdate" in str(e):
            logger.error(f"PositionUpdate model does not exist. Skipping update: {e}")

            # Create a temporary object to return
            class TempUpdate:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            return TempUpdate(**update.dict())
        else:
            # Re-raise other exceptions
            raise e


def get_position_updates(db: Session, signal_id: int):
    try:
        return db.query(models.PositionUpdate).filter(
            models.PositionUpdate.signal_id == signal_id
        ).order_by(models.PositionUpdate.created_at).all()
    except Exception as e:
        # Check if the PositionUpdate model exists
        if "models" in str(e) and "PositionUpdate" in str(e):
            logger.error(f"PositionUpdate model does not exist. Returning empty list: {e}")
            return []
        else:
            # Re-raise other exceptions
            raise e


# Transaction operations
def create_transaction(db: Session, transaction: schemas.TransactionCreate):
    db_transaction = models.Transaction(
        user_id=transaction.user_id,
        amount=transaction.amount,
        transaction_type=transaction.transaction_type,
        details=transaction.details
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def get_user_transactions(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id
    ).order_by(models.Transaction.created_at.desc()).offset(skip).limit(limit).all()


# Package operations
def get_packages(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Package).filter(
        models.Package.is_active == True
    ).offset(skip).limit(limit).all()


def get_package(db: Session, package_id: int):
    return db.query(models.Package).filter(models.Package.id == package_id).first()


def create_package(db: Session, package: schemas.PackageCreate):
    db_package = models.Package(
        name=package.name,
        signals_count=package.signals_count,
        price=package.price
    )
    db.add(db_package)
    db.commit()
    db.refresh(db_package)
    return db_package


# User Signal operations
def create_user_signal(db: Session, user_id: int, signal_id: int):
    db_user_signal = models.UserSignal(
        user_id=user_id,
        signal_id=signal_id
    )
    db.add(db_user_signal)
    db.commit()
    db.refresh(db_user_signal)

    # Deduct one signal from user's signals balance
    update_signals_balance(db, user_id, -1)

    # Record transaction
    transaction = schemas.TransactionCreate(
        user_id=user_id,
        amount=1,
        transaction_type=schemas.TransactionType.SIGNAL_USED,
        details=f"Signal ID: {signal_id}"
    )
    create_transaction(db, transaction)

    return db_user_signal


def get_users_by_signal(db: Session, signal_id: int):
    return db.query(models.User).join(
        models.UserSignal
    ).filter(
        models.UserSignal.signal_id == signal_id
    ).all()


# Daily summary operations
def get_daily_summary(db: Session, date_obj: date):
    signals = get_signals_by_date(db, date_obj)

    # Calculate total profit
    total_profit = 0.0
    for signal in signals:
        if signal.profit_percentage:
            total_profit += signal.profit_percentage

    return {
        "date": date_obj,
        "signals": signals,
        "total_profit": total_profit
    }