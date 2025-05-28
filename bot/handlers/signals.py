from keyboards import get_main_menu, get_packages_keyboard, get_back_keyboard
from aiogram import Router, F, types
import logging
import aiohttp
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
from config import settings


router = Router()
logger = logging.getLogger(__name__)


# Helper function to get user from API
async def get_user(telegram_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/users/{telegram_id}") as response:
                if response.status == 404:
                    return None
                return await response.json()
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None


# Helper function to purchase signals
async def purchase_signals(telegram_id: int, package_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{settings.API_URL}/api/users/{telegram_id}/purchase_signals",
                    params={"package_id": package_id}
            ) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error purchasing signals: {e}")
        return None


@router.message(F.text == "💰 Купить сигнал")
async def buy_signal(message: types.Message):
    await message.answer(
        "📦 Выберите количество сигналов:",
        reply_markup=get_packages_keyboard()
    )


@router.callback_query(F.data.startswith("package_"))
async def package_callback(callback: types.CallbackQuery):
    package_id = int(callback.data.split("_")[1])

    # Get package details
    package = None
    for p in settings.DEFAULT_PACKAGES:
        if p["id"] == package_id:
            package = p
            break

    if not package:
        await callback.message.edit_text(
            "❌ Пакет не найден. Пожалуйста, выберите другой пакет.",
            reply_markup=get_packages_keyboard()
        )
        await callback.answer()
        return

    # Get user data
    user_data = await get_user(callback.from_user.id)
    if not user_data:
        await callback.message.edit_text(
            "❌ Ошибка при получении данных. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return

    # Purchase signals (in real implementation, this would involve payment)
    # For demonstration, let's simulate successful purchase
    result = await purchase_signals(callback.from_user.id, package_id)

    if result and result.get("success"):
        await callback.message.edit_text(
            f"✅ Поздравляем! Вы успешно приобрели {package['signals_count']} сигналов.\n\n"
            f"Ваш новый баланс: {result['new_balance']} сигналов",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при покупке сигналов. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_back_keyboard()
        )

    await callback.answer()


async def get_daily_summary(date_str: str) -> Dict[str, Any]:
    """Get daily summary from API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/daily_summary/{date_str}") as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception as e:
        logger.error(f"Error getting daily summary: {e}")
        return None


# Helper function to get signals in date range
async def get_signals_in_range(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """Get all signals in a date range by fetching daily summaries."""
    all_signals = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        daily_summary = await get_daily_summary(date_str)

        if daily_summary and daily_summary.get('signals'):
            all_signals.extend(daily_summary['signals'])

        current_date += timedelta(days=1)

    return all_signals


# Helper function to calculate statistics from signals
def calculate_stats(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics from a list of signals."""
    if not signals:
        return {
            'total_signals': 0,
            'successful_signals': 0,
            'total_profit': 0.0,
            'average_profit': 0.0,
            'success_rate': 0.0
        }

    total_signals = len(signals)
    successful_signals = sum(1 for signal in signals if signal.get('profit_percentage', 0) > 0)
    total_profit = sum(signal.get('profit_percentage', 0) for signal in signals)
    average_profit = total_profit / total_signals if total_signals > 0 else 0
    success_rate = (successful_signals / total_signals * 100) if total_signals > 0 else 0

    return {
        'total_signals': total_signals,
        'successful_signals': successful_signals,
        'total_profit': total_profit,
        'average_profit': average_profit,
        'success_rate': success_rate
    }


@router.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Show actual trading statistics fetched from the API."""

    # Send a "loading" message
    loading_msg = await message.answer("📈 Загружаю статистику...")

    try:
        # Get current date
        today = date.today()

        # Get today's stats
        today_str = today.strftime("%Y-%m-%d")
        today_summary = await get_daily_summary(today_str)

        # Format today's section
        today_text = "📅 <b>За сегодня:</b>\n"
        if today_summary and today_summary.get('signals'):
            for signal in today_summary['signals']:
                profit = signal.get('profit_percentage', 0)
                profit_str = f"+{profit:.1f}%" if profit > 0 else f"{profit:.1f}%"
                profit_emoji = "🟢" if profit > 0 else "🔴"
                today_text += f"Сделка №{signal['signal_number']:05d}: {profit_emoji} {profit_str}\n"

            total_profit = today_summary.get('total_profit', 0)
            total_profit_str = f"+{total_profit:.1f}%" if total_profit > 0 else f"{total_profit:.1f}%"
            today_text += f"\n<b>Общая прибыль:</b> {total_profit_str}\n"
        else:
            today_text += "Сигналов пока не было\n"

        await loading_msg.edit_text(today_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await loading_msg.edit_text(
            "❌ Произошла ошибка при загрузке статистики.\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )



# Internal endpoint for sending signals to users
# @router.post("/internal/send_signal")
# async def send_signal_to_users(request: Dict[str, Any]):
#     """Send a signal to users based on signal type."""
#     try:
#         signal_id = request.get("signal_id")
#         user_ids = request.get("user_ids", [])
#
#         # Fetch signal details from API
#         async with aiohttp.ClientSession() as session:
#             async with session.get(f"{settings.API_URL}/api/signals/{signal_id}") as response:
#                 if response.status != 200:
#                     return {"status": "error", "message": f"Failed to fetch signal: {await response.text()}"}
#                 signal = await response.json()
#
#         # Format signal message based on action
#         if signal['action'] == 'open':
#             signal_message = format_entry_signal(signal)
#         elif signal['action'] == 'partial_close':
#             signal_message = format_partial_close_signal(signal)
#         elif signal['action'] == 'close':
#             signal_message = format_exit_signal(signal)
#         elif signal['action'] == 'increase':
#             signal_message = format_increase_signal(signal)
#         else:
#             signal_message = format_entry_signal(signal)  # Default
#
#         # Send signal to each user
#         from main import bot
#         for user_id in user_ids:
#             try:
#                 # Record signal usage in API (only for entry signals)
#                 if signal['action'] == 'open':
#                     async with aiohttp.ClientSession() as session:
#                         async with session.post(
#                                 f"{settings.API_URL}/api/signals/{signal_id}/users/{user_id}"
#                         ) as response:
#                             if response.status != 200:
#                                 logger.error(f"Failed to record signal use: {await response.text()}")
#                                 continue
#
#                 # Get user's Telegram ID
#                 async with aiohttp.ClientSession() as session:
#                     async with session.get(f"{settings.API_URL}/api/users/by_id/{user_id}") as response:
#                         if response.status != 200:
#                             logger.error(f"Failed to get user: {await response.text()}")
#                             continue
#                         user = await response.json()
#
#                 # Send message to user
#                 await bot.send_message(
#                     user["telegram_id"],
#                     signal_message,
#                     parse_mode="HTML"
#                 )
#             except Exception as e:
#                 logger.error(f"Error sending signal to user {user_id}: {e}")
#
#         return {"status": "success", "message": f"Signal sent to {len(user_ids)} users"}
#     except Exception as e:
#         logger.error(f"Error in send_signal_to_users: {e}")
#         return {"status": "error", "message": str(e)}
#


def format_entry_signal(signal: Dict[str, Any]) -> str:
    """Format entry signal message."""
    category_emoji = "🔍" if signal['category'] == 'SPOT' else "⚡"
    direction = "🟩 Новая сделка\n\nLONG" if signal['signal_type'] == 'BUY' else "🟩 Новая сделка\n\nSHORT"
    symbol = signal['symbol'] if not signal['symbol'].endswith('USDT') else signal['symbol'][:-4] + '/' + 'USDT'
    message = (
        f"<b>Сделка №{signal['signal_number']:05d}</b>\n\n"
        f"<b>{direction} {symbol}</b>\n"
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

    entry_time = entry_time + timedelta(hours=3)
    message += f"\n\n⏱ {entry_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_partial_close_signal(signal: Dict[str, Any]) -> str:
    """Format partial close signal message with enhanced information."""
    direction = "🟧 Частичное закрытие\n\nLONG" if signal['signal_type'] == 'BUY' else "🟧 Частичное закрытие\n\nSHORT"
    symbol = signal['symbol'] if not signal['symbol'].endswith('USDT') else signal['symbol'][:-4] + '/' + 'USDT'
    # Calculate remaining percentage
    remaining_percentage = 100 - int(signal['close_percentage'])

    message = (
        f"<b>Сделка №{signal['signal_number']:05d}</b>\n\n"
        f"<b>{direction} {symbol}</b>\n"
        f"<b>Закрыто:</b> {int(signal['close_percentage'])}%\n"
        # f"<b>Цена закрытия:</b> {signal.get('exit_price', 'N/A')}\n"
        f"<b>Осталось:</b> {signal['position_size']} ({remaining_percentage}%)"
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
        exit_time = exit_time + timedelta(hours=3)
        message += f"\n\n⏱ {exit_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_exit_signal(signal: Dict[str, Any]) -> str:
    """Format exit signal message with enhanced information."""
    category_emoji = "🔍" if signal['category'] == 'SPOT' else "⚡"
    direction = "🟥 Закрытие сделки\n\nLONG" if signal['signal_type'] == 'BUY' else "🟥 Закрытие сделки\n\nSHORT"
    symbol = signal['symbol'] if not signal['symbol'].endswith('USDT') else signal['symbol'][:-4] + '/' + 'USDT'
    message = (
        f"<b>Сделка №{signal['signal_number']:05d}</b>\n\n"
        f"<b>{direction} {symbol}</b>\n"
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
    exit_time = exit_time + timedelta(hours=3)
    message += f"\n\n⏱ {exit_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message


def format_increase_signal(signal: Dict[str, Any]) -> str:
    """Format position increase signal message with enhanced information."""
    direction = "🟨 Увеличение позиции\n\nLONG" if signal['signal_type'] == 'BUY' else "🟨 Увеличение позиции\n\nSHORT"
    symbol = signal['symbol'] if not signal['symbol'].endswith('USDT') else signal['symbol'][:-4] + '/' + 'USDT'

    # Calculate increase percentage
    old_size = float(signal['old_position_size']) if signal.get('old_position_size') else 0
    new_size = float(signal['position_size']) if signal.get('position_size') else 0

    if old_size > 0:
        increase_percentage = ((new_size - old_size) / old_size) * 100
    else:
        increase_percentage = 100

    message = (
        f"📈 <b>Сделка №{signal['signal_number']:05d}</b>\n\n"
        f"<b>{direction} {symbol}</b>\n"
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

        entry_time = entry_time + timedelta(hours=3)
        message += f"\n\n⏱ {entry_time.strftime('%H:%M:%S %d.%m.%Y')}"

    return message