from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
import logging
import aiohttp
from datetime import datetime
from typing import List, Dict, Any
from config import settings
from keyboards import get_main_menu, get_packages_keyboard, get_back_keyboard

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


# Handler for receiving signals
@router.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    # Here you would fetch statistics from API
    # For demonstration, we'll show a simulated response

    stats_text = (
        "📊 Статистика торговых сигналов:\n\n"
        "За сегодня:\n"
        "Сделка №00001: +10.5%\n"
        "Сделка №00002: +7.6%\n\n"
        "Общая прибыль: +18.1%\n\n"
        "За неделю:\n"
        "Успешных сделок: 12/15\n"
        "Средняя прибыль: +8.7%\n\n"
        "За месяц:\n"
        "Успешных сделок: 42/50\n"
        "Средняя прибыль: +12.3%"
    )

    await message.answer(stats_text)


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