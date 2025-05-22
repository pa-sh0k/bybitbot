#!/usr/bin/env python3
"""
Database migration script to update the schema for USDT balance functionality
Run this script to migrate from the old schema to the new one.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Database connection
def get_database_url():

    # Fallback to individual components
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "")
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    database = os.getenv("PG_DATABASE", "postgres")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def migrate_database():
    """Migrate the database schema to support USDT balance"""
    try:
        engine = create_engine(get_database_url())

        with engine.begin() as conn:
            logger.info("Starting database migration...")

            # 1. Add new columns to users table if they don't exist
            try:
                logger.info("Adding usdt_balance column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS usdt_balance FLOAT DEFAULT 0.0;"))
                logger.info("✓ usdt_balance column added")
            except Exception as e:
                logger.warning(f"Could not add usdt_balance column: {e}")

            try:
                logger.info("Adding signals_balance column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS signals_balance INTEGER DEFAULT 0;"))
                logger.info("✓ signals_balance column added")
            except Exception as e:
                logger.warning(f"Could not add signals_balance column: {e}")

            # 2. Migrate data from old balance column to signals_balance if old column exists
            try:
                logger.info("Checking for old 'balance' column...")
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='balance';
                """))

                if result.fetchone():
                    logger.info("Found old balance column, migrating data...")

                    # Copy data from balance to signals_balance
                    conn.execute(text("""
                        UPDATE users 
                        SET signals_balance = COALESCE(balance, 0) 
                        WHERE signals_balance = 0 AND balance IS NOT NULL;
                    """))

                    logger.info("✓ Data migrated from balance to signals_balance")

                    # Optional: Drop the old balance column (commented out for safety)
                    # conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS balance;"))
                    # logger.info("✓ Old balance column dropped")
                else:
                    logger.info("No old balance column found, skipping data migration")

            except Exception as e:
                logger.warning(f"Could not migrate balance data: {e}")

            # 3. Update transaction types enum
            try:
                logger.info("Updating transaction types enum...")
                conn.execute(text("""
                    DO $$
                    BEGIN
                        -- Add new enum values if they don't exist
                        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'USDT_DEPOSIT' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transactiontype')) THEN
                            ALTER TYPE transactiontype ADD VALUE 'USDT_DEPOSIT';
                        END IF;
                    EXCEPTION
                        WHEN others THEN
                            -- Enum might not exist yet, create it
                            CREATE TYPE transactiontype AS ENUM ('USDT_DEPOSIT', 'SIGNAL_PURCHASE', 'SIGNAL_USED');
                    END
                    $$;
                """))
                logger.info("✓ Transaction types enum updated")
            except Exception as e:
                logger.warning(f"Could not update transaction types enum: {e}")

            # 4. Set default values for existing users
            try:
                logger.info("Setting default values for existing users...")
                conn.execute(text("""
                    UPDATE users 
                    SET usdt_balance = 0.0 
                    WHERE usdt_balance IS NULL;
                """))

                conn.execute(text("""
                    UPDATE users 
                    SET signals_balance = 0 
                    WHERE signals_balance IS NULL;
                """))
                logger.info("✓ Default values set for existing users")
            except Exception as e:
                logger.warning(f"Could not set default values: {e}")

            logger.info("Database migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


def verify_migration():
    """Verify that the migration was successful"""
    try:
        engine = create_engine(get_database_url())

        with engine.begin() as conn:
            logger.info("Verifying migration...")

            # Check if new columns exist
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name IN ('usdt_balance', 'signals_balance')
                ORDER BY column_name;
            """))

            columns = result.fetchall()

            if len(columns) == 2:
                logger.info("✓ Migration verification successful!")
                for col in columns:
                    logger.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
            else:
                logger.error(f"❌ Migration verification failed! Expected 2 columns, found {len(columns)}")
                return False

            # Check if there are any users and their balance structure
            result = conn.execute(text("SELECT COUNT(*) FROM users;"))
            user_count = result.scalar()

            if user_count > 0:
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_users,
                        AVG(usdt_balance) as avg_usdt,
                        AVG(signals_balance) as avg_signals
                    FROM users;
                """))
                stats = result.fetchone()
                logger.info(
                    f"✓ User statistics: {stats[0]} users, avg USDT: {stats[1]:.2f}, avg signals: {stats[2]:.2f}")

            return True

    except Exception as e:
        logger.error(f"Migration verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=== Database Migration Script ===")
    logger.info("This script will migrate your database to support USDT balance functionality")

    # Check database connection
    try:
        engine = create_engine(get_database_url())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Run migration
    migrate_database()

    # Verify migration
    if verify_migration():
        logger.info("🎉 Migration completed successfully!")
    else:
        logger.error("❌ Migration verification failed!")
        sys.exit(1)