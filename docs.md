# Bybit Integration Guide

This document explains how the trading signals bot integrates with Bybit API v5 to monitor positions and generate signals.

## Overview

Since Bybit API v5 doesn't provide webhooks for trade monitoring, our system uses **active polling** to track position changes in real-time.

## How It Works

### 1. Position Tracking

The system continuously monitors positions using the Bybit API:
- **Spot Trading**: Tracks buy/sell orders and position changes
- **Futures Trading**: Tracks long/short positions with leverage
- **Polling Interval**: Configurable (default: 5 seconds)

### 2. Signal Generation

Signals are generated based on position changes:

#### Entry Signals (`OPEN`)
- **Trigger**: New position detected
- **Data**: Symbol, direction (BUY/SELL), position size, leverage, entry price
- **Notification**: Sent to all users with positive signal balance

#### Partial Close Signals (`PARTIAL_CLOSE`)
- **Trigger**: Position size decreased (partial close)
- **Data**: Percentage closed, remaining position size
- **Notification**: Sent to users who received the entry signal

#### Exit Signals (`CLOSE`)
- **Trigger**: Position completely closed (size = 0)
- **Data**: Exit price, realized P&L, profit percentage
- **Notification**: Sent to users who received the entry signal

#### Position Increase (`INCREASE`)
- **Trigger**: Position size increased (adding to position)
- **Data**: New position size, old position size
- **Notification**: Sent to users who received the entry signal

### 3. Message Formats

#### Entry Signal
```
🔔 Сделка №00001 ⚡

📈 LONG BTC/USDT
Цена входа: 45000.0
Размер позиции: 1.0
Плечо: 10x

⏱ 14:30:25 16.05.2025
```

#### Partial Close Signal
```
🔄 Сделка №00001 - Частичное закрытие

📈 LONG BTC/USDT
Закрыто: 50.0%
Осталось: 0.5
Частичная прибыль: +250.5 USDT
```

#### Exit Signal
```
🔚 Сделка №00001 ⚡

📈 LONG BTC/USDT
Цена выхода: 47000.0
Размер позиции: 1.0
Плечо: 10x
💰 Прибыль: +4.44%
Прибыль: +500.0 USDT

⏱ 14:45:12 16.05.2025
```

## Setup Instructions

### 1. Bybit API Credentials

1. Create a Bybit account
2. Go to API Management
3. Create new API key with permissions:
   - **Read Position**: Required for position monitoring
   - **Read Order**: Required for execution data
   - **Read Wallet**: Optional for balance checks

### 2. Configuration

Add to your `.env` file:
```env
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=true  # Use testnet for development
SIGNAL_POLL_INTERVAL=5  # Check every 5 seconds
```

### 3. Testing

Use the manual signal endpoints for testing:

#### Create Test Signal
```bash
curl -X POST "http://localhost/api/signals/test" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "signal_type": "buy",
    "category": "linear",
    "leverage": "10",
    "position_size": "1.0",
    "entry_price": "45000"
  }'
```

#### Close Test Signal
```bash
curl -X POST "http://localhost/api/signals/1/close" \
  -H "Content-Type: application/json" \
  -d '{
    "exit_price": "47000",
    "profit_percentage": 4.44
  }'
```

## Position Tracking Logic

### Database Schema

The system tracks positions with the following data:

```sql
signals:
- id, signal_number (sequential)
- symbol (e.g., BTCUSDT)
- category (spot, linear, inverse)
- signal_type (buy, sell)
- action (open, partial_close, close, increase)
- position_size, old_position_size
- entry_price, exit_price
- leverage (for futures)
- close_percentage, realized_pnl
- profit_percentage

position_updates:
- signal_id (foreign key)
- action, position_size
- close_percentage, realized_pnl
- created_at
```

### Position State Management

1. **New Position**: Creates signal with action='open'
2. **Size Decrease**: Updates signal with action='partial_close'
3. **Complete Close**: Updates signal with action='close', marks completed
4. **Size Increase**: Updates signal with action='increase'

### Error Handling

- **API Errors**: Logged and retried with exponential backoff
- **Network Issues**: Automatic reconnection
- **Invalid Data**: Skipped with warning log
- **Database Errors**: Rollback and retry

## Monitoring

### Health Checks

- **API Connectivity**: Verified every poll cycle
- **Position Tracking**: Status reported in logs
- **Database Health**: Connection monitoring

### Logging

All position changes are logged with:
- Timestamp
- Position details
- Action taken
- Users notified

### Metrics (Optional)

If monitoring is enabled:
- Signals generated per hour
- API response times
- Error rates
- User notification success rates

## Security Considerations

1. **API Keys**: Stored as environment variables
2. **Rate Limiting**: Respects Bybit API limits
3. **IP Whitelisting**: Recommended for production
4. **Read-Only Keys**: Only read permissions needed

## Troubleshooting

### Common Issues

1. **No Signals Generated**
   - Check API credentials
   - Verify position exists in Bybit
   - Check polling is active

2. **Delayed Notifications**
   - Reduce poll interval
   - Check API response times
   - Verify database performance

3. **Missing Partial Closes**
   - Ensure position size tracking is accurate
   - Check for API data inconsistencies

### Debug Mode

Enable debug logging:
```env
LOG_LEVEL=DEBUG
```

This will log all position changes and API responses.

## Performance Optimization

1. **Efficient Polling**: Only fetch positions that have changed
2. **Database Indexing**: Proper indexes on frequently queried fields
3. **Async Processing**: Non-blocking signal distribution
4. **Connection Pooling**: Reuse API connections

## Limitations

1. **Spot Trading**: Limited position tracking compared to futures
2. **Multiple Positions**: Same symbol/direction tracked as one signal
3. **Complex Strategies**: Advanced order types may not be tracked properly
4. **Historical Data**: Only tracks positions from service start time

## Future Enhancements

1. **WebSocket Integration**: If Bybit adds WebSocket position updates
2. **Multiple Accounts**: Support for tracking multiple trader accounts
3. **Advanced Analytics**: Detailed performance metrics
4. **Strategy Detection**: Automatic pattern recognition