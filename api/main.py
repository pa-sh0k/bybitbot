from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import List, Dict, Any
import os
import logging
import asyncio
import sys
from datetime import date, datetime, timedelta
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
        # Create enum types and tables in separate transactions
        await create_enum_types()
        await create_tables()
        await create_default_packages()
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


async def create_enum_types():
    """Create enum types if they don't exist."""
    try:
        with engine.begin() as conn:
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
    except Exception as e:
        logger.error(f"Error creating enum types: {e}")
        raise


async def create_tables():
    """Create tables if they don't exist."""
    try:
        with engine.begin() as conn:
            # Check if users table exists and has correct schema
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
            """))
            existing_columns = [row[0] for row in result]

            if 'users' not in [table.name for table in Base.metadata.tables.values()] or not existing_columns:
                # Create users table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR,
                        first_name VARCHAR,
                        last_name VARCHAR,
                        usdt_balance FLOAT NOT NULL DEFAULT 0,
                        signals_balance FLOAT NOT NULL DEFAULT 0,
                        role userrole NOT NULL DEFAULT 'USER',
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                    CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);
                """))
                logger.info("Created users table")
            else:
                # Check if balance column exists, if not add it
                if 'balance' not in existing_columns:
                    conn.execute(text("""
                        ALTER TABLE users ADD COLUMN balance INTEGER NOT NULL DEFAULT 0;
                    """))
                    logger.info("Added balance column to users table")

            # Create signals table
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

            # Create other tables...
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_signals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    signal_id INTEGER REFERENCES signals(id),
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

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

                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    amount FLOAT NOT NULL,
                    transaction_type transactiontype NOT NULL,
                    details VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

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
            logger.info("Created remaining tables")

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


async def create_default_packages():
    """Create default packages if they don't exist."""
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
        raise

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


@app.get("/api/users/by_id/{user_id}", response_model=schemas.User)
def read_user_by_id(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.post("/api/users/{telegram_id}/add_usdt_balance")
def add_usdt_balance(
        telegram_id: int, balance_update: schemas.BalanceUpdate, db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=telegram_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if balance_update.usdt_amount is None:
        raise HTTPException(status_code=400, detail="USDT amount is required")

    response = crud.update_usdt_balance(db, db_user.id, balance_update.usdt_amount, balance_update.transaction_id)

    if response['success'] and not response['duplicate']:
        # Record transaction
        transaction = schemas.TransactionCreate(
            user_id=db_user.id,
            amount=balance_update.usdt_amount,
            transaction_type=schemas.TransactionType.DEPOSIT,
            details=f"USDT balance deposit | transaction_id:{balance_update.transaction_id}"
        )
        crud.create_transaction(db, transaction)

    user = response['user']
    return {"success": True, "usdt_balance": user.usdt_balance, "signals_balance": user.signals_balance, 'duplicate': user['duplicate']}


@app.post("/api/users/{telegram_id}/purchase_signals")
def purchase_signals(
        telegram_id: int, purchase_request: schemas.PurchaseSignalsRequest, db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_telegram_id(db, telegram_id=telegram_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = crud.purchase_signals_with_usdt(db, db_user.id, purchase_request.package_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Purchase failed"))

    return result


@app.get("/api/packages/", response_model=List[schemas.Package])
def read_packages(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    packages = crud.get_packages(db, skip=skip, limit=limit)
    return packages


@app.get("/api/users/active")
def get_active_users(db: Session = Depends(get_db)):
    """Get all active users for broadcasting"""
    users = db.query(models.User).filter(models.User.is_active == True).all()
    return [{"id": user.id, "telegram_id": user.telegram_id} for user in users]


@app.get("/api/daily_summary/{date_str}")
def get_daily_summary(date_str: str, db: Session = Depends(get_db)):
    # Calculate today's date in UTC+3
    utc_plus_3_offset = 3 * 60 * 60  # 3 hours in seconds
    now_utc = datetime.utcnow()
    now_utc3 = now_utc + timedelta(seconds=utc_plus_3_offset)
    today_utc3 = now_utc3.date()

    summary = crud.get_daily_summary(db, today_utc3)
    return summary


# Signal endpoints
@app.get("/api/signals/{signal_id}")
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = crud.get_signal(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@app.get("/api/signals/{signal_id}/users")
def get_signal_users(signal_id: int, db: Session = Depends(get_db)):
    users = crud.get_users_by_signal(db, signal_id)
    return [{"id": user.id, "telegram_id": user.telegram_id} for user in users]


@app.post("/api/signals/{signal_id}/users/{user_id}")
def record_signal_usage(signal_id: int, user_id: int, db: Session = Depends(get_db)):
    """Record that a user received a signal"""
    try:
        user_signal = crud.create_user_signal(db, user_id, signal_id)
        return {"success": True, "message": "Signal usage recorded"}
    except Exception as e:
        logger.error(f"Error recording signal usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to record signal usage")


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

        # Get users with positive signals balance
        users = crud.get_users_with_signals_balance(db)
        user_ids = [user.id for user in users]

        # Send signal in background using bot_api
        if user_ids:
            from bot_api import send_signal_to_users
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
        from bot_api import send_exit_signal_to_users
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
# Add this endpoint to your api/main.py file

@app.post("/api/bot/send_message")
async def send_bot_message(
        request: dict,  # Use dict instead of specific model for flexibility
        background_tasks: BackgroundTasks = None
):
    """Send a message to a user via the bot service"""
    try:
        telegram_id = request.get("telegram_id")
        message = request.get("message")

        if not telegram_id or not message:
            raise HTTPException(status_code=400, detail="telegram_id and message are required")

        # Send message via bot service
        from bot_api import send_message
        if background_tasks:
            background_tasks.add_task(
                send_message,
                telegram_id=telegram_id,
                message=message
            )
        else:
            asyncio.create_task(send_message(telegram_id, message))

        return {"success": True, "message": "Message queued for sending"}

    except Exception as e:
        logger.error(f"Error in send_bot_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)