from typing import Dict, Any
from datetime import datetime

def format_entry_signal(signal: Dict[str, Any]) -> str:
    """Format entry signal message."""
    category_emoji = "🔍" if signal['category'] == 'SPOT' else "⚡"
    direction = "📈 LONG" if signal['signal_type'] == 'BUY' else "📉 SHORT"

    message = (
        f"🔔 <b>Сделка №{signal['signal_number']:05d}</b> {category_emoji}\n\n"
        f"<b>{direction} {signal['symbol']}</b>\n"
        f"<b>Цена входа:</b> {signal['entry_price']}\n"
        f"<b>Размер позиции:</b> {signal['position_size']}"
    )

    # Add leverage for futures
    if signal['category'] in ['LINEAR', 'INVERSE']:
        message += f"\n<b>Плечо:</b> {signal['leverage']}x"

    # Add timestamp
    entry_time = datetime.fromisoformat(signal['entry_time'].replace('Z', '+00:00')) if isinstance(signal['entry_time'],
                                                                                                   str) else signal[
        'entry_time']
    message += f"\n\n⏱ {entry_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_partial_close_signal(signal: Dict[str, Any]) -> str:
    """Format partial close signal message with enhanced information."""
    direction = "📈 LONG" if signal['signal_type'] == 'BUY' else "📉 SHORT"

    # Calculate remaining percentage
    remaining_percentage = 100 - signal['close_percentage']

    message = (
        f"🔄 <b>Сделка №{signal['signal_number']:05d}</b> - Частичное закрытие\n\n"
        f"<b>{direction} {signal['symbol']}</b>\n"
        f"<b>Закрыто:</b> {signal['close_percentage']:.1f}%\n"
        f"<b>Цена закрытия:</b> {signal.get('exit_price', 'N/A')}\n"
        f"<b>Осталось:</b> {signal['position_size']} ({remaining_percentage:.1f}%)"
    )

    # Add average entry price if available
    if signal.get('entry_price'):
        message += f"\n<b>Средняя цена входа:</b> {signal['entry_price']}"

    # Add partial profit information if available
    if signal.get('realized_pnl') and signal['realized_pnl'] != '0':
        pnl = float(signal['realized_pnl'])
        pnl_str = f"+{pnl:.2f}" if pnl > 0 else f"{pnl:.2f}"
        message += f"\n<b>Частичная прибыль:</b> {pnl_str} USDT"

    # Add timestamp if available
    if signal.get('exit_time'):
        exit_time = datetime.fromisoformat(signal['exit_time'].replace('Z', '+00:00')) if isinstance(
            signal['exit_time'], str) else signal['exit_time']
        message += f"\n\n⏱ {exit_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_exit_signal(signal: Dict[str, Any]) -> str:
    """Format exit signal message with enhanced information."""
    category_emoji = "🔍" if signal['category'] == 'SPOT' else "⚡"
    direction = "📈 LONG" if signal['signal_type'] == 'BUY' else "📉 SHORT"

    message = (
        f"🔚 <b>Сделка №{signal['signal_number']:05d}</b> {category_emoji}\n\n"
        f"<b>{direction} {signal['symbol']}</b>\n"
        f"<b>Средняя цена входа:</b> {signal['entry_price']}\n"
        f"<b>Средняя цена выхода:</b> {signal['exit_price']}\n"
        f"<b>Размер позиции:</b> {signal['old_position_size']}"
    )

    # Add leverage for futures
    if signal['category'] in ['LINEAR', 'INVERSE']:
        message += f"\n<b>Плечо:</b> {signal['leverage']}x"

    # Add profit/loss
    if signal.get('profit_percentage') is not None:
        profit = signal['profit_percentage']
        profit_str = f"+{profit:.2f}%" if profit > 0 else f"{profit:.2f}%"
        profit_emoji = "💰" if profit > 0 else "💸"
        message += f"\n<b>{profit_emoji} Прибыль:</b> {profit_str}"

    if signal.get('realized_pnl') and signal['realized_pnl'] != '0':
        pnl = float(signal['realized_pnl'])
        pnl_str = f"+{pnl:.2f}" if pnl > 0 else f"{pnl:.2f}"
        message += f"\n<b>Прибыль:</b> {pnl_str} USDT"

    # Add timestamp
    exit_time = datetime.fromisoformat(signal['exit_time'].replace('Z', '+00:00')) if isinstance(signal['exit_time'],
                                                                                                 str) else signal[
        'exit_time']
    message += f"\n\n⏱ {exit_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_increase_signal(signal: Dict[str, Any]) -> str:
    """Format position increase signal message with enhanced information."""
    direction = "📈 LONG" if signal['signal_type'] == 'BUY' else "📉 SHORT"

    # Calculate increase percentage
    old_size = float(signal['old_position_size']) if signal.get('old_position_size') else 0
    new_size = float(signal['position_size']) if signal.get('position_size') else 0

    if old_size > 0:
        increase_percentage = ((new_size - old_size) / old_size) * 100
    else:
        increase_percentage = 100

    message = (
        f"📈 <b>Сделка №{signal['signal_number']:05d}</b> - Увеличение позиции\n\n"
        f"<b>{direction} {signal['symbol']}</b>\n"
        f"<b>Увеличение на:</b> {increase_percentage:.1f}%\n"
        f"<b>Новый размер:</b> {signal['position_size']}\n"
        f"<b>Было:</b> {signal['old_position_size']}"
    )

    # Add new entry price if available
    if signal.get('entry_price'):
        message += f"\n<b>Средняя цена входа:</b> {signal['entry_price']}"

    # Add timestamp if available
    if signal.get('entry_time'):
        entry_time = datetime.fromisoformat(signal['entry_time'].replace('Z', '+00:00')) if isinstance(
            signal['entry_time'], str) else signal['entry_time']
        message += f"\n\n⏱ {entry_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message