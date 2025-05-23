import time
import hmac
import hashlib
from datetime import datetime

import requests
import json
import websocket
import threading
from typing import Dict, Any, Optional, List
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class BybitClientV5:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.base_url = "https://api.bybit.com"
            self.ws_url = "wss://stream.bybit.com/v5/private"

        self.recv_window = 5000

    def _generate_signature(self, timestamp: str, params: str) -> str:
        """Generate signature for Bybit API v5 authentication."""
        param_str = f"{timestamp}{self.api_key}{self.recv_window}{params}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request to the Bybit API v5."""
        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(time.time() * 1000))

        if params is None:
            params = {}

        if method == "GET":
            param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        else:
            param_str = json.dumps(params) if params else ""

        signature = self._generate_signature(timestamp, param_str)

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json"
        }

        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Bybit API: {e}")
            return {"retCode": -1, "retMsg": str(e), "result": {}}

    def get_positions(self, category: str = "linear", symbol: Optional[str] = None, settle_coin: Optional[str] = None) -> Dict[str, Any]:
        """Get position information. Categories: spot, linear, inverse, option."""
        endpoint = "/v5/position/list"
        params = {"category": category}

        if symbol:
            params["symbol"] = symbol

        if settle_coin:
            params["settleCoin"] = settle_coin

        return self._make_request("GET", endpoint, params)

    def get_execution_list(self, category: str = "linear", symbol: Optional[str] = None, limit: int = 50) -> Dict[
        str, Any]:
        """Get recent executions (filled orders)."""
        endpoint = "/v5/execution/list"
        params = {
            "category": category,
            "limit": limit
        }

        if symbol:
            params["symbol"] = symbol

        return self._make_request("GET", endpoint, params)

    def get_open_orders(self, category: str = "linear", symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get open orders."""
        endpoint = "/v5/order/realtime"
        params = {"category": category}

        if symbol:
            params["symbol"] = symbol

        return self._make_request("GET", endpoint, params)

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Get wallet balance. Account types: UNIFIED, CONTRACT, SPOT."""
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": account_type}
        return self._make_request("GET", endpoint, params)

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        endpoint = "/v5/account/info"
        return self._make_request("GET", endpoint)


class BybitPositionTracker:
    def __init__(self, client: BybitClientV5, db_callback=None):
        self.client = client
        self.db_callback = db_callback
        self.is_running = False
        self.tracked_positions = {}  # symbol -> position_data
        self.tracked_categories = ["linear"]  # Track futures and spot

    def start_tracking(self, poll_interval: int = 5):
        """Start position tracking with polling."""
        self.is_running = True

        def track_positions():
            while self.is_running:
                try:
                    self._check_positions()
                    time.sleep(poll_interval)
                except Exception as e:
                    logger.error(f"Error in position tracking: {e}")
                    time.sleep(poll_interval)

        tracking_thread = threading.Thread(target=track_positions, daemon=True)
        tracking_thread.start()
        logger.info("Started position tracking")

    def stop_tracking(self):
        """Stop position tracking."""
        self.is_running = False
        logger.info("Stopped position tracking")

    def _check_positions(self):
        """Check for position changes."""
        # Track all position keys we see in this update cycle
        current_position_keys = set()

        for category in self.tracked_categories:
            try:
                response = self.client.get_positions(category=category, settle_coin="USDT")

                if response.get("retCode") == 0:
                    positions = response.get("result", {}).get("list", [])
                    self._process_positions(positions, category)

                    # Add all position keys we found to the tracking set
                    for position in positions:
                        symbol = position.get("symbol")
                        side = position.get("side")
                        size = Decimal(position.get("size", "0"))

                        # Only track non-zero positions
                        if size > 0:
                            position_key = f"{category}_{symbol}_{side}"
                            current_position_keys.add(position_key)
                else:
                    logger.error(f"Error fetching positions: {response.get('retMsg')}")

            except Exception as e:
                logger.error(f"Error checking positions for {category}: {e}")

        # Find positions that are no longer in the list but were tracked
        closed_positions = set(self.tracked_positions.keys()) - current_position_keys

        # Handle positions that disappeared (closed without going through size=0)
        for position_key in closed_positions:
            if position_key in self.tracked_positions:
                self._handle_position_close_by_disappearance(position_key)

    def _process_positions(self, positions: List[Dict], category: str):
        """Process position data and detect changes."""
        for position in positions:
            symbol = position.get("symbol")
            side = position.get("side")
            size = Decimal(position.get("size", "0"))
            leverage = position.get("leverage", "1")
            avg_price = Decimal(position.get("avgPrice", "0"))
            mark_price = Decimal(position.get("markPrice", "0"))
            unrealized_pnl = Decimal(position.get("unrealisedPnl", "0"))
            percentage = Decimal(position.get("unrealisedPnlPc", "0")) * 100

            position_key = f"{category}_{symbol}_{side}"

            # Skip empty positions
            if size == 0:
                # If we were tracking this position and now it's closed
                if position_key in self.tracked_positions:
                    self._handle_position_close(position_key, position, category)
                continue

            # New position detected
            if position_key not in self.tracked_positions:
                self._handle_position_open(position_key, position, category)
            else:
                # Check for position size changes
                old_size = self.tracked_positions[position_key].get("size", Decimal("0"))
                old_avg_price = self.tracked_positions[position_key].get("avg_price", Decimal("0"))

                if size != old_size:
                    # Size changed - determine if increase or decrease
                    if size > old_size:
                        # Position size increased
                        self._handle_position_increase(position_key, position, category, old_size, old_avg_price)
                    else:
                        # Position partially closed
                        self._handle_position_partial_close(position_key, position, category, old_size, old_avg_price)

            # Update tracked position
            self.tracked_positions[position_key] = {
                "symbol": symbol,
                "side": side,
                "size": size,
                "leverage": leverage,
                "avg_price": avg_price,
                "mark_price": mark_price,
                "unrealized_pnl": unrealized_pnl,
                "percentage": percentage,
                "category": category,
                "last_update": time.time()
            }

    def _handle_position_open(self, position_key: str, position: Dict, category: str):
        """Handle new position opening."""
        try:
            logger.info(f"New position opened: {position_key}")

            if self.db_callback:
                signal_data = {
                    "symbol": position.get("symbol"),
                    "side": position.get("side"),
                    "size": position.get("size"),
                    "leverage": position.get("leverage", "1"),
                    "avg_price": position.get("avgPrice"),
                    "category": category,
                    "action": "OPEN"
                }
                self.db_callback(signal_data)
        except Exception as e:
            logger.error(f"Error in position open handler: {e}", exc_info=True)

    def _handle_position_increase(self, position_key: str, position: Dict, category: str, old_size: Decimal,
                                  old_avg_price: Decimal):
        """Handle position size increase with enhanced price tracking."""
        try:
            new_size = Decimal(position.get("size", "0"))
            new_avg_price = Decimal(position.get("avgPrice", "0"))

            # Calculate size increase
            size_increase = new_size - old_size
            increase_percentage = (size_increase / old_size) * 100 if old_size > 0 else 100

            logger.info(f"Position increased: {position_key} by {increase_percentage:.2f}%")

            if self.db_callback:
                signal_data = {
                    "symbol": position.get("symbol"),
                    "side": position.get("side"),
                    "size": str(new_size),
                    "old_size": str(old_size),
                    "category": category,
                    "action": "INCREASE",
                    "avg_price": position.get("avgPrice"),  # New average price
                    "old_avg_price": str(old_avg_price),  # Old average price
                    "increase_percentage": float(increase_percentage)
                }
                self.db_callback(signal_data)
        except Exception as e:
            logger.error(f"Error in position increase handler: {e}", exc_info=True)

    def _handle_position_partial_close(self, position_key: str, position: Dict, category: str, old_size: Decimal,
                                       old_avg_price: Decimal):
        """Handle position partial close with enhanced price tracking."""
        try:
            new_size = Decimal(position.get("size", "0"))
            new_avg_price = Decimal(position.get("avgPrice", "0"))

            # Calculate the size that was closed
            closed_size = old_size - new_size
            close_percentage = (closed_size / old_size) * 100

            logger.info(f"Position partially closed: {position_key}, {close_percentage:.2f}%")

            # Get execution history to find PnL and exit price
            executions = self.client.get_execution_list(
                category=category,
                symbol=position.get("symbol"),
                limit=10
            )

            realized_pnl = Decimal("0")
            exit_price = None

            if executions.get("retCode") == 0:
                exec_list = executions.get("result", {}).get("list", [])
                # Find the most recent execution with opposite side (closing trade)
                for exec in exec_list:
                    # For closures, the side is opposite of the position
                    if exec.get("side") != position.get("side"):
                        realized_pnl += Decimal(exec.get("closedPnl", "0"))
                        exit_price = exec.get("price")
                        break

            if self.db_callback:
                signal_data = {
                    "symbol": position.get("symbol"),
                    "side": position.get("side"),
                    "size": str(new_size),
                    "old_size": str(old_size),
                    "close_percentage": float(close_percentage),
                    "category": category,
                    "action": "PARTIAL_CLOSE",
                    "avg_price": position.get("avgPrice"),  # Current average price
                    "exit_price": exit_price,  # Price at which the partial close happened
                    "realized_pnl": str(realized_pnl)
                }
                self.db_callback(signal_data)
        except Exception as e:
            logger.error(f"Error in partial close handler: {e}", exc_info=True)

    def _handle_position_close(self, position_key: str, position: Dict, category: str):
        """Handle position complete close with enhanced price tracking."""
        try:
            old_position = self.tracked_positions[position_key]
            logger.info(f"Position completely closed: {position_key}")

            # Get execution history to find PnL and exit prices
            executions = self.client.get_execution_list(
                category=category,
                symbol=old_position["symbol"],
                limit=20  # Get more executions to better calculate average exit price
            )

            realized_pnl = Decimal("0")
            exit_prices = []
            exit_quantities = []
            exit_time = None

            if executions.get("retCode") == 0:
                exec_list = executions.get("result", {}).get("list", [])

                # Find all closing executions and calculate weighted average exit price
                for exec in exec_list:
                    if exec.get("side") != old_position["side"]:  # Closing trade
                        realized_pnl += Decimal(exec.get("closedPnl", "0"))

                        # Record exit price and quantity for weighted average
                        exec_price = Decimal(exec.get("price", "0"))
                        exec_qty = Decimal(exec.get("orderQty", "0"))

                        if exec_price > 0 and exec_qty > 0:
                            exit_prices.append(exec_price)
                            exit_quantities.append(exec_qty)

                        # Get the most recent exit time
                        if not exit_time and exec.get("execTime"):
                            try:
                                exit_time = datetime.fromtimestamp(int(exec.get("execTime")) / 1000)
                            except:
                                try:
                                    exit_time = datetime.fromisoformat(exec.get("execTime").replace('Z', '+00:00'))
                                except:
                                    exit_time = datetime.now()

            # Calculate weighted average exit price
            avg_exit_price = None
            if exit_prices and exit_quantities:
                total_quantity = sum(exit_quantities)
                if total_quantity > 0:
                    weighted_sum = sum(p * q for p, q in zip(exit_prices, exit_quantities))
                    avg_exit_price = weighted_sum / total_quantity

            # If we couldn't determine exit price from executions, use last known mark price
            if not avg_exit_price and "mark_price" in old_position:
                avg_exit_price = old_position["mark_price"]

            # Calculate profit percentage based on entry and exit prices
            profit_percentage = None
            if avg_exit_price and "avg_price" in old_position and old_position["avg_price"] > 0:
                entry_price = old_position["avg_price"]

                if old_position["side"].upper() == "BUY":
                    # For long positions: (exit - entry) / entry * 100
                    profit_percentage = (avg_exit_price - entry_price) / entry_price * 100
                else:
                    # For short positions: (entry - exit) / entry * 100
                    profit_percentage = (entry_price - avg_exit_price) / entry_price * 100

            if self.db_callback:
                signal_data = {
                    "symbol": old_position["symbol"],
                    "side": old_position["side"],
                    "size": "0",
                    "old_size": str(old_position["size"]),
                    "close_percentage": 100.0,
                    "realized_pnl": str(realized_pnl),
                    "category": category,
                    "action": "CLOSE",
                    "avg_price": str(old_position["avg_price"]),  # Entry price
                    "exit_price": str(avg_exit_price) if avg_exit_price else None,  # Average exit price
                    "exit_time": exit_time,
                    "profit_percentage": float(profit_percentage) if profit_percentage is not None else None
                }
                self.db_callback(signal_data)

            # Remove from tracked positions
            del self.tracked_positions[position_key]
        except Exception as e:
            logger.error(f"Error in position close handler: {e}", exc_info=True)

    def _handle_position_close_by_disappearance(self, position_key: str):
        """Handle when a position disappears from the positions list (closed)."""
        try:
            logger.info(f"Position disappeared (closed): {position_key}")

            if position_key not in self.tracked_positions:
                return

            old_position = self.tracked_positions[position_key]

            # Split the key to get category, symbol, side
            category, symbol, side = position_key.split("_")

            # Get execution history to find PnL and exit prices
            executions = self.client.get_execution_list(
                category=category,
                symbol=symbol,
                limit=20  # Get more executions to better calculate average exit price
            )

            realized_pnl = Decimal("0")
            exit_prices = []
            exit_quantities = []
            exit_time = None

            if executions.get("retCode") == 0:
                exec_list = executions.get("result", {}).get("list", [])

                # Find all closing executions and calculate weighted average exit price
                for exec in exec_list:
                    if exec.get("side") != side:  # Closing trade
                        realized_pnl += Decimal(exec.get("closedPnl", "0"))

                        # Record exit price and quantity for weighted average
                        exec_price = Decimal(exec.get("price", "0"))
                        exec_qty = Decimal(exec.get("orderQty", "0"))

                        if exec_price > 0 and exec_qty > 0:
                            exit_prices.append(exec_price)
                            exit_quantities.append(exec_qty)

                        # Get the most recent exit time
                        if not exit_time and exec.get("execTime"):
                            try:
                                exit_time = datetime.fromtimestamp(int(exec.get("execTime")) / 1000)
                            except:
                                try:
                                    exit_time = datetime.fromisoformat(exec.get("execTime").replace('Z', '+00:00'))
                                except:
                                    exit_time = datetime.now()

            # Calculate weighted average exit price
            avg_exit_price = None
            if exit_prices and exit_quantities:
                total_quantity = sum(exit_quantities)
                if total_quantity > 0:
                    weighted_sum = sum(p * q for p, q in zip(exit_prices, exit_quantities))
                    avg_exit_price = weighted_sum / total_quantity

            # If we couldn't determine exit price from executions, use last known mark price
            if not avg_exit_price and "mark_price" in old_position:
                avg_exit_price = old_position["mark_price"]

            # Calculate profit percentage based on entry and exit prices
            profit_percentage = None
            if avg_exit_price and "avg_price" in old_position and old_position["avg_price"] > 0:
                entry_price = old_position["avg_price"]

                if old_position["side"].upper() == "BUY":
                    # For long positions: (exit - entry) / entry * 100
                    profit_percentage = (avg_exit_price - entry_price) / entry_price * 100
                else:
                    # For short positions: (entry - exit) / entry * 100
                    profit_percentage = (entry_price - avg_exit_price) / entry_price * 100

            if self.db_callback:
                signal_data = {
                    "symbol": old_position["symbol"],
                    "side": old_position["side"],
                    "size": "0",
                    "old_size": str(old_position["size"]),
                    "close_percentage": 100.0,
                    "realized_pnl": str(realized_pnl),
                    "category": category,
                    "action": "CLOSE",
                    "avg_price": str(old_position["avg_price"]),  # Entry price
                    "exit_price": str(avg_exit_price) if avg_exit_price else None,  # Average exit price
                    "exit_time": exit_time or datetime.now(),
                    "profit_percentage": float(profit_percentage) if profit_percentage is not None else None
                }
                self.db_callback(signal_data)

            # Remove from tracked positions
            del self.tracked_positions[position_key]
        except Exception as e:
            logger.error(f"Error handling position disappearance: {e}", exc_info=True)

class BybitWebSocketClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        if testnet:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"

        self.ws = None
        self.callbacks = {}

    def _generate_auth_signature(self, expires: int) -> str:
        """Generate auth signature for WebSocket."""
        param_str = f"GET/realtime{expires}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def connect(self):
        """Connect to WebSocket and authenticate."""

        def on_open(ws):
            logger.info("WebSocket connection opened")
            self._authenticate()

        def on_message(ws, message):
            try:
                data = json.loads(message)
                self._handle_message(data)
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")

        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.info("WebSocket connection closed")

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        # Start WebSocket in a separate thread
        ws_thread = threading.Thread(target=self.ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

    def _authenticate(self):
        """Authenticate WebSocket connection."""
        expires = int(time.time() * 1000) + 10000
        signature = self._generate_auth_signature(expires)

        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        self.ws.send(json.dumps(auth_message))

    def subscribe(self, topics: List[str], callback=None):
        """Subscribe to WebSocket topics."""
        for topic in topics:
            self.callbacks[topic] = callback

        subscribe_message = {
            "op": "subscribe",
            "args": topics
        }
        self.ws.send(json.dumps(subscribe_message))

    def _handle_message(self, data: Dict):
        """Handle incoming WebSocket messages."""
        topic = data.get("topic", "")

        if topic in self.callbacks and self.callbacks[topic]:
            self.callbacks[topic](data)
        elif "success" in data:
            logger.info(f"WebSocket operation successful: {data}")
        elif "error" in data:
            logger.error(f"WebSocket error: {data}")