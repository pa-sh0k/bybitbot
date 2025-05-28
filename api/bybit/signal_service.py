import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
import sys
import os
import threading

# Add the api directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, api_dir)

from sqlalchemy.orm import Session

from .client import BybitClientV5, BybitPositionTracker
from database import SessionLocal
import crud, models, schemas
from bot_api import send_signal_to_users, send_exit_signal_to_users

logger = logging.getLogger(__name__)


class BybitSignalService:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.client = BybitClientV5(api_key, api_secret, testnet)
        self.tracker = BybitPositionTracker(self.client, self._handle_position_update)
        self.active_signals = {}  # Track open signals by position key

        # Create a new event loop for async operations
        self.loop = asyncio.new_event_loop()
        self.thread = None

    def _start_background_loop(self):
        """Start the event loop in a background thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _initialize_active_signals(self):
        """Initialize active_signals with existing open positions from database and Bybit."""
        try:
            logger.info("Initializing active signals from database and Bybit...")

            with SessionLocal() as db:
                # Get all open signals from database
                open_signals = crud.get_open_signals(db)
                logger.info(f"Found {len(open_signals)} open signals in database")

                # Get current positions from Bybit for all categories
                current_bybit_positions = {}

                for category in self.tracker.tracked_categories:
                    try:
                        response = self.client.get_positions(category=category, settle_coin="USDT")
                        if response.get("retCode") == 0:
                            positions = response.get("result", {}).get("list", [])

                            for position in positions:
                                symbol = position.get("symbol")
                                side = position.get("side").upper()
                                size = Decimal(position.get("size", "0"))

                                # Only track non-zero positions
                                if size > 0:
                                    position_key = f"{category}_{symbol}_{side}"
                                    current_bybit_positions[position_key] = {
                                        "symbol": symbol,
                                        "side": side,
                                        "size": size,
                                        "category": category,
                                        "position_data": position
                                    }
                        else:
                            logger.error(f"Error fetching positions for {category}: {response.get('retMsg')}")
                    except Exception as e:
                        logger.error(f"Error fetching positions for {category}: {e}")

                logger.info(f"Found {len(current_bybit_positions)} active positions on Bybit")

                # Match database signals with Bybit positions
                matched_count = 0
                for signal in open_signals:
                    try:
                        # Convert signal data to position key format
                        category = signal.category.value.lower()
                        symbol = signal.symbol
                        side = signal.signal_type.value.lower().capitalize()  # BUY or SELL

                        position_key = f"{category}_{symbol}_{side}"

                        # Check if this signal matches a current Bybit position
                        if position_key in current_bybit_positions:
                            self.active_signals[position_key] = signal.id
                            matched_count += 1
                            logger.debug(f"Matched signal {signal.signal_number} with position {position_key}")

                            # Update tracker's tracked positions with current state
                            bybit_position = current_bybit_positions[position_key]["position_data"]
                            self.tracker.tracked_positions[position_key] = {
                                "symbol": symbol,
                                "side": side,
                                "size": Decimal(bybit_position.get("size", "0")),
                                "leverage": bybit_position.get("leverage", "1"),
                                "avg_price": Decimal(bybit_position.get("avgPrice", "0")),
                                "mark_price": Decimal(bybit_position.get("markPrice", "0")),
                                "unrealized_pnl": Decimal(bybit_position.get("unrealisedPnl", "0")),
                                "percentage": Decimal(bybit_position.get("unrealisedPnlPc", "0")) * 100,
                                "category": category,
                                "last_update": datetime.now().timestamp()
                            }
                        else:
                            # Signal exists in database but no corresponding position on Bybit
                            # This could mean the position was closed outside our tracking
                            logger.warning(
                                f"Signal {signal.signal_number} ({position_key}) exists in DB but not on Bybit - position may have been closed externally")

                    except Exception as e:
                        logger.error(f"Error processing signal {signal.id}: {e}")

                logger.info(f"Successfully matched {matched_count} database signals with Bybit positions")

                # Check for Bybit positions that don't have corresponding database signals
                untracked_positions = []
                for position_key, position_info in current_bybit_positions.items():
                    if position_key not in self.active_signals:
                        untracked_positions.append(position_key)

                if untracked_positions:
                    logger.warning(f"Found {len(untracked_positions)} Bybit positions without database signals:")
                    for pos_key in untracked_positions:
                        logger.warning(f"  - {pos_key}")
                    logger.warning(
                        "These positions were likely opened before the service started or outside our tracking")

                logger.info(f"Active signals initialization complete. Tracking {len(self.active_signals)} positions.")

        except Exception as e:
            logger.error(f"Error initializing active signals: {e}", exc_info=True)

    def start(self, poll_interval: int = 5):
        """Start the signal service."""
        logger.info("Starting Bybit signal service...")

        # Start the event loop in a background thread
        self.thread = threading.Thread(target=self._start_background_loop, daemon=True)
        self.thread.start()

        # Initialize active signals from existing data
        self._initialize_active_signals()

        # Start position tracking
        self.tracker.start_tracking(poll_interval)

    def stop(self):
        """Stop the signal service."""
        logger.info("Stopping Bybit signal service...")
        self.tracker.stop_tracking()

        # Stop the event loop
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_async(self, coro):
        """Run a coroutine in the event loop."""
        if self.loop and self.loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            logger.error("Event loop is not running, cannot execute async task")
            return None

    def _handle_position_update(self, signal_data: Dict[str, Any]):
        """Handle position updates from the tracker."""
        try:
            # Print the signal_data for debugging
            logger.debug(f"Received position update: {signal_data}")

            with SessionLocal() as db:
                action = signal_data.get("action").lower()

                if action == "open":
                    self._handle_position_open(db, signal_data)
                elif action == "partial_close":
                    self._handle_position_partial_close(db, signal_data)
                elif action == "close":
                    self._handle_position_close(db, signal_data)
                elif action == "increase":
                    self._handle_position_increase(db, signal_data)
                else:
                    logger.warning(f"Unknown action type: {action}")

        except Exception as e:
            logger.error(f"Error handling position update: {e}", exc_info=True)

    def _handle_position_open(self, db: Session, signal_data: Dict[str, Any]):
        """Handle new position opening."""
        position_key = f"{signal_data['category']}_{signal_data['symbol']}_{signal_data['side']}"

        # Check if we're already tracking this position
        if position_key in self.active_signals:
            logger.warning(
                f"Position {position_key} is already being tracked as signal {self.active_signals[position_key]}")
            return

        # Create new signal
        signal_create = schemas.SignalCreate(
            symbol=signal_data["symbol"],
            category=self._get_signal_category(signal_data["category"]),
            signal_type=self._get_signal_type(signal_data["side"]),
            action=schemas.SignalAction.OPEN,
            position_size=signal_data["size"],
            leverage=signal_data.get("leverage", "1"),
            entry_price=signal_data.get("avg_price"),
            entry_time=datetime.now()
        )

        signal = crud.create_signal(db, signal_create)

        # Store reference for tracking
        self.active_signals[position_key] = signal.id

        # Send signal to users - use the event loop to run the async task
        self._run_async(self._notify_users_entry(signal))

        logger.info(f"New signal created: {signal.signal_number} - {signal.symbol} {signal.signal_type}")

    def _handle_position_partial_close(self, db: Session, signal_data: Dict[str, Any]):
        """Handle partial position closure."""
        position_key = f"{signal_data['category']}_{signal_data['symbol']}_{signal_data['side']}"

        if position_key not in self.active_signals:
            logger.warning(f"No active signal found for partial close: {position_key}")
            return

        signal_id = self.active_signals[position_key]

        # Update signal with partial close info
        signal_update = schemas.SignalUpdate(
            entry_price=signal_data["avg_price"],
            action=schemas.SignalAction.PARTIAL_CLOSE,
            position_size=signal_data["size"],
            old_position_size=signal_data["old_size"],
            close_percentage=signal_data["close_percentage"]
        )

        signal = crud.update_signal(db, signal_id, signal_update)

        # Create position update record
        update_create = schemas.PositionUpdateCreate(
            signal_id=signal_id,
            action=schemas.SignalAction.PARTIAL_CLOSE,
            position_size=signal_data["size"],
            close_percentage=signal_data["close_percentage"]
        )
        crud.create_position_update(db, update_create)

        # Send partial close notification - use the event loop
        self._run_async(self._notify_users_partial_close(signal, signal_data["close_percentage"]))

        logger.info(f"Signal {signal.signal_number} partially closed: {signal_data['close_percentage']:.2f}%")

    def _handle_position_close(self, db: Session, signal_data: Dict[str, Any]):
        """Handle complete position closure."""
        try:
            position_key = f"{signal_data['category']}_{signal_data['symbol']}_{signal_data['side']}"

            if position_key not in self.active_signals:
                logger.warning(f"No active signal found for close: {position_key}")
                return

            signal_id = self.active_signals[position_key]

            # Calculate profit percentage if not provided
            profit_percentage = signal_data.get("profit_percentage")
            if profit_percentage is None:
                profit_percentage = self._calculate_profit_percentage(signal_data)

            # Get exit price and time from signal_data
            exit_price = signal_data.get("exit_price")
            exit_time = signal_data.get("exit_time", datetime.now())

            # Update signal with close info
            signal_update = schemas.SignalUpdate(
                action=schemas.SignalAction.CLOSE,
                position_size="0",
                old_position_size=signal_data["old_size"],
                exit_price=exit_price,
                exit_time=exit_time,
                close_percentage=100.0,
                realized_pnl=signal_data.get("realized_pnl", "0"),
                profit_percentage=profit_percentage
            )

            signal = crud.update_signal(db, signal_id, signal_update)
            signal = crud.mark_signal_completed(db, signal_id)

            # Try to create position update record (catch error if model doesn't exist)
            try:
                update_create = schemas.PositionUpdateCreate(
                    signal_id=signal_id,
                    action=schemas.SignalAction.CLOSE,
                    position_size="0",
                    price=exit_price,
                    close_percentage=100.0,
                    realized_pnl=signal_data.get("realized_pnl", "0")
                )
                crud.create_position_update(db, update_create)
            except Exception as e:
                logger.warning(f"Could not create position update: {e}")

            # Remove from active signals
            del self.active_signals[position_key]

            # Send close notification - use the event loop
            self._run_async(self._notify_users_exit(signal))

            logger.info(f"Signal {signal.signal_number} fully closed: {profit_percentage:.2f}%")
        except Exception as e:
            logger.error(f"Error in _handle_position_close: {e}", exc_info=True)

    def _handle_position_increase(self, db: Session, signal_data: Dict[str, Any]):
        """Handle position size increase."""
        position_key = f"{signal_data['category']}_{signal_data['symbol']}_{signal_data['side']}"

        if position_key not in self.active_signals:
            logger.warning(f"No active signal found for increase: {position_key}")
            return

        signal_id = self.active_signals[position_key]

        # Update signal with increased size
        signal_update = schemas.SignalUpdate(
            entry_price=signal_data["avg_price"],
            action=schemas.SignalAction.INCREASE,
            position_size=signal_data["size"],
            old_position_size=signal_data["old_size"]
        )

        signal = crud.update_signal(db, signal_id, signal_update)

        # Create position update record
        update_create = schemas.PositionUpdateCreate(
            signal_id=signal_id,
            action=schemas.SignalAction.INCREASE,
            position_size=signal_data["size"]
        )
        crud.create_position_update(db, update_create)

        # Send increase notification - use the event loop
        self._run_async(self._notify_users_increase(signal))

        logger.info(f"Signal {signal.signal_number} position increased")

    def _get_signal_category(self, bybit_category: str) -> schemas.SignalCategory:
        """Convert Bybit category to signal category."""
        bybit_category = bybit_category.upper()

        if bybit_category == "LINEAR":
            return schemas.SignalCategory.LINEAR
        elif bybit_category == "INVERSE":
            return schemas.SignalCategory.INVERSE
        else:
            return schemas.SignalCategory.SPOT

    def _get_signal_type(self, bybit_side: str) -> schemas.SignalType:
        """Convert Bybit side to signal type."""
        # Make sure we match the enum case exactly
        if bybit_side.upper() == "BUY":
            return schemas.SignalType.BUY
        else:
            return schemas.SignalType.SELL

    def _calculate_profit_percentage(self, signal_data: Dict[str, Any]) -> float:
        """Calculate profit percentage from realized PnL."""
        try:
            realized_pnl = Decimal(signal_data.get("realized_pnl", "0"))
            old_size = Decimal(signal_data.get("old_size", "1"))

            if old_size == 0:
                return 0.0

            # Simple percentage calculation - this may need adjustment based on actual data
            return float(realized_pnl / old_size * 100)
        except:
            return 0.0

    async def _notify_users_entry(self, signal: models.Signal):
        """Notify users about new signal entry."""
        with SessionLocal() as db:
            # Use the new function name for signals balance
            users = crud.get_users_with_signals_balance(db)
            user_ids = [user.id for user in users]

            if user_ids:
                from bot_api import send_signal_to_users
                try:
                    await send_signal_to_users(signal.id, user_ids)
                except Exception as e:
                    logger.error(f"Error notifying users of entry signal: {e}")

    async def _notify_users_partial_close(self, signal: models.Signal, close_percentage: float):
        """Notify users about partial close."""
        with SessionLocal() as db:
            users = crud.get_users_by_signal(db, signal.id)
            user_ids = [user.id for user in users]

            if user_ids:
                from bot_api import send_signal_to_users
                try:
                    await send_signal_to_users(signal.id, user_ids)
                except Exception as e:
                    logger.error(f"Error notifying users of partial close: {e}")

    async def _notify_users_exit(self, signal: models.Signal):
        """Notify users about signal exit."""
        from bot_api import send_exit_signal_to_users
        try:
            await send_exit_signal_to_users(signal.id)
        except Exception as e:
            logger.error(f"Error notifying users of exit signal: {e}")

    async def _notify_users_increase(self, signal: models.Signal):
        """Notify users about position increase."""
        with SessionLocal() as db:
            users = crud.get_users_by_signal(db, signal.id)
            user_ids = [user.id for user in users]

            if user_ids:
                from bot_api import send_signal_to_users
                try:
                    await send_signal_to_users(signal.id, user_ids)
                except Exception as e:
                    logger.error(f"Error notifying users of position increase: {e}")

    def get_active_signals_status(self) -> Dict[str, Any]:
        """Get current status of active signals for debugging/monitoring."""
        return {
            "active_signals_count": len(self.active_signals),
            "tracked_positions_count": len(self.tracker.tracked_positions),
            "active_signals": dict(self.active_signals),
            "service_running": self.tracker.is_running if hasattr(self.tracker, 'is_running') else "unknown"
        }