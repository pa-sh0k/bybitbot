from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import List, Dict, Any
import os
import logging
import asyncio
import sys
from datetime import date, datetime
from contextlib import asynccontextmanager

# Import models, schemas, and database
import crud, models, schemas
from database import engine, get_db, Base, SessionLocal
from bybit.signal_service import BybitSignalService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global signal service instance
signal_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the FastAPI application."""
    # Database initialization - create tables if they don't exist
    logger.info("Initializing database...")

    try:
        # First, create the enum types if they don't exist
        with engine.begin() as conn:
            # Create enum types
            enum_types = [
                ("signaltype", "('BUY', 'SELL')"),
                ("signalcategory", "('SPOT', 'LINEAR', 'INVERSE')"),
                ("signalaction", "('OPEN', 'PARTIAL_CLOSE', 'CLOSE', 'INCREASE')"),
                ("userrole", "('USER', 'ADMIN')"),
                ("transactiontype", "('DEPOSIT', 'SIGNAL_PURCHASE', 'SIGNAL_USED')")
            ]

            for enum_name, enum_values in enum_types:
                try:
                    conn.execute(text(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN
                                CREATE TYPE {enum_name} AS ENUM {enum_values};
                            END IF;
                        END
                        $$;
                    """))
                    logger.info(f"Checked/created enum type: {enum_name}")
                except Exception as e:
                    logger.error(f"Error creating enum type {enum_name}: {e}")

        # Create tables one by one in the correct order
        with engine.begin() as conn:
            # 1. Create users table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR,
                    first_name VARCHAR,
                    last_name VARCHAR,
                    balance INTEGER NOT NULL DEFAULT 0,
                    role userrole NOT NULL DEFAULT 'USER',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            """))
            logger.info("Created users table")

            # 2. Create signals table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY,
                    signal_number INTEGER NOT NULL,
                    symbol VARCHAR NOT NULL,
                    category signalcategory NOT NULL,
                    signal_type signaltype NOT NULL,
                    action signalaction,
                    position_size VARCHAR NOT NULL,
                    old_position_size VARCHAR,
                    entry_price VARCHAR,
                    exit_price VARCHAR,
                    leverage VARCHAR NOT NULL DEFAULT '1',
                    close_percentage FLOAT,
                    realized_pnl VARCHAR,
                    unrealized_pnl VARCHAR,
                    profit_percentage FLOAT,
                    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
                    exit_time TIMESTAMP WITH TIME ZONE,
                    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_signals_signal_number ON signals (signal_number);
                CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals (symbol);
            """))
            logger.info("Created signals table")

            # 3. Create user_signals table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_signals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    signal_id INTEGER REFERENCES signals(id),
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            logger.info("Created user_signals table")

            # 4. Create position_updates table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS position_updates (
                    id SERIAL PRIMARY KEY,
                    signal_id INTEGER REFERENCES signals(id),
                    action signalaction NOT NULL,
                    position_size VARCHAR NOT NULL,
                    price VARCHAR,
                    close_percentage FLOAT,
                    realized_pnl VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            logger.info("Created position_updates table")

            # 5. Create transactions table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    amount FLOAT NOT NULL,
                    transaction_type transactiontype NOT NULL,
                    details VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            logger.info("Created transactions table")

            # 6. Create packages table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS packages (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    signals_count INTEGER NOT NULL,
                    price FLOAT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            """))
            logger.info("Created packages table")

        # Verify tables were created
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Tables in database: {sorted(existing_tables)}")

        # Create default packages if they don't exist
        try:
            with SessionLocal() as db:
                # Check if packages already exist
                if db.query(models.Package).count() == 0:
                    # Default packages
                    packages = [
                        models.Package(name="Basic", signals_count=1, price=1.0, is_active=True),
                        models.Package(name="Standard", signals_count=10, price=9.0, is_active=True),
                        models.Package(name="Premium", signals_count=30, price=25.0, is_active=True),
                        models.Package(name="VIP", signals_count=100, price=75.0, is_active=True)
                    ]

                    # Add packages to database
                    for package in packages:
                        db.add(package)

                    db.commit()
                    logger.info(f"Created default packages")
        except Exception as e:
            logger.error(f"Error creating default packages: {e}")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True)
        logger.warning("Continuing startup despite database initialization error")

    # Bybit API service initialization
    global signal_service
    bybit_api_key = os.getenv("BYBIT_API_KEY")
    bybit_api_secret = os.getenv("BYBIT_API_SECRET")
    bybit_testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"

    if bybit_api_key and bybit_api_secret:
        try:
            signal_service = BybitSignalService(bybit_api_key, bybit_api_secret, bybit_testnet)
            signal_service.start(poll_interval=5)  # Check every 5 seconds
            logger.info("Started Bybit signal service")
        except Exception as e:
            logger.error(f"Error starting Bybit signal service: {e}", exc_info=True)
    else:
        logger.warning("Bybit API credentials not found. Signal service disabled.")

    yield

    # Shutdown - stop signal service if running
    if signal_service:
        try:
            signal_service.stop()
            logger.info("Stopped Bybit signal service")
        except Exception as e:
            logger.error(f"Error stopping Bybit signal service: {e}", exc_info=True)


app = FastAPI(title="Trading Signals API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API endpoints for TG bot
@app.post("/api/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=user.telegram_id)
    if db_user:
        return db_user
    return crud.create_user(db=db, user=user)


@app.get("/api/users/{telegram_id}", response_model=schemas.User)
def read_user(telegram_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=telegram_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.post("/api/users/{telegram_id}/add_balance")
def add_user_balance(
        telegram_id: int, amount: int, db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=telegram_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = crud.update_user_balance(db, db_user.id, amount)

    # Record transaction
    transaction = schemas.TransactionCreate(
        user_id=db_user.id,
        amount=amount,
        transaction_type=schemas.TransactionType.DEPOSIT,
        details="Balance deposit"
    )
    crud.create_transaction(db, transaction)

    return {"success": True, "new_balance": updated_user.balance}


@app.post("/api/users/{telegram_id}/purchase_signals")
def purchase_signals(
        telegram_id: int, package_id: int, db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=telegram_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db_package = crud.get_package(db, package_id)
    if db_package is None:
        raise HTTPException(status_code=404, detail="Package not found")

    # Add signals to user's balance
    updated_user = crud.update_user_balance(db, db_user.id, db_package.signals_count)

    # Record transaction
    transaction = schemas.TransactionCreate(
        user_id=db_user.id,
        amount=db_package.price,
        transaction_type=schemas.TransactionType.SIGNAL_PURCHASE,
        details=f"Purchased {db_package.signals_count} signals for {db_package.price} USDT"
    )
    crud.create_transaction(db, transaction)

    return {
        "success": True,
        "new_balance": updated_user.balance,
        "package": db_package.name,
        "signals_added": db_package.signals_count
    }


@app.get("/api/packages/", response_model=List[schemas.Package])
def read_packages(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    packages = crud.get_packages(db, skip=skip, limit=limit)
    return packages


@app.get("/api/daily_summary/{date}")
def get_daily_summary(date_str: str, db: Session = Depends(get_db)):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    summary = crud.get_daily_summary(db, date_obj)
    return summary


# Manual signal testing endpoint (for development/testing)
@app.post("/api/signals/test")
async def create_test_signal(
        symbol: str,
        signal_type: str,
        category: str = "linear",
        leverage: str = "10",
        position_size: str = "1.0",
        entry_price: str = "50000",
        background_tasks: BackgroundTasks = None,
        db: Session = Depends(get_db)
):
    """Create a test signal (for development/testing purposes)."""
    try:
        # Create test signal
        signal_create = schemas.SignalCreate(
            symbol=symbol,
            category=schemas.SignalCategory(category),
            signal_type=schemas.SignalType(signal_type),
            action=schemas.SignalAction.OPEN,
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            entry_time=datetime.now()
        )

        signal = crud.create_signal(db, signal_create)

        # Get users with positive balance
        users = crud.get_users_with_balance(db)
        user_ids = [user.id for user in users]

        # Send signal in background using bot_api
        if user_ids:
            from app.bot_api import send_signal_to_users
            if background_tasks:
                background_tasks.add_task(
                    send_signal_to_users,
                    signal_id=signal.id,
                    user_ids=user_ids
                )
            else:
                # Run directly if no background tasks
                asyncio.create_task(send_signal_to_users(signal.id, user_ids))

        return {
            "success": True,
            "signal_id": signal.id,
            "signal_number": signal.signal_number,
            "users_notified": len(user_ids)
        }
    except Exception as e:
        logger.error(f"Error creating test signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Manual signal close endpoint
@app.post("/api/signals/{signal_id}/close")
async def close_test_signal(
        signal_id: int,
        exit_price: str,
        profit_percentage: float = 0.0,
        background_tasks: BackgroundTasks = None,
        db: Session = Depends(get_db)
):
    """Close a test signal (for development/testing purposes)."""
    try:
        signal = crud.get_signal(db, signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        # Update signal with close info
        signal_update = schemas.SignalUpdate(
            action=schemas.SignalAction.CLOSE,
            position_size="0",
            old_position_size=signal.position_size,
            exit_price=exit_price,
            exit_time=datetime.now(),
            close_percentage=100.0,
            profit_percentage=profit_percentage
        )

        updated_signal = crud.update_signal(db, signal_id, signal_update)
        crud.mark_signal_completed(db, signal_id)

        # Send close notification using bot_api
        from app.bot_api import send_exit_signal_to_users
        if background_tasks:
            background_tasks.add_task(
                send_exit_signal_to_users,
                signal_id=signal_id
            )
        else:
            # Run directly if no background tasks
            asyncio.create_task(send_exit_signal_to_users(signal_id))

        return {
            "success": True,
            "signal_id": signal_id,
            "profit_percentage": profit_percentage
        }
    except Exception as e:
        logger.error(f"Error closing test signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Bot API endpoint for sending messages
@app.post("/api/bot/send_message")
async def send_bot_message(
        telegram_id: int,
        message: str,
        background_tasks: BackgroundTasks = None
):
    from bot_api import send_message
    if background_tasks:
        background_tasks.add_task(
            send_message,
            telegram_id=telegram_id,
            message=message
        )
    else:
        asyncio.create_task(send_message(telegram_id, message))
    return {"success": True}


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)