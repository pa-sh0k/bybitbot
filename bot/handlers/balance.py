from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import aiohttp
from datetime import datetime

from config import settings
from keyboards import (
    get_main_menu, get_balance_menu, get_usdt_deposit_amounts_keyboard,
    get_cancel_keyboard, get_back_keyboard, get_buy_signals_menu,
    get_packages_keyboard, get_package_confirm_keyboard, get_back_to_balance_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


# States
class DepositStates(StatesGroup):
    waiting_for_usdt_amount = State()
    waiting_for_payment = State()


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


# Helper function to add USDT balance to user
async def add_usdt_balance(telegram_id: int, amount: float):
    try:
        async with aiohttp.ClientSession() as session:
            params = {"usdt_amount": amount}
            async with session.post(f"{settings.API_URL}/api/users/{telegram_id}/add_usdt_balance",
                                    json=params) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error adding USDT balance: {e}")
        return None


# Helper function to purchase signals with USDT
async def purchase_signals(telegram_id: int, package_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            params = {"package_id": package_id}
            async with session.post(f"{settings.API_URL}/api/users/{telegram_id}/purchase_signals",
                                    json=params) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error purchasing signals: {e}")
        return None


@router.message(F.text == "💼 Баланс")
async def show_balance(message: types.Message):
    # Get user data
    user_data = await get_user(message.from_user.id)
    if not user_data:
        await message.answer(
            "❌ Ошибка при получении данных. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        return

    # Show both USDT and signals balance
    balance_text = (
        f"💼 <b>Ваш баланс:</b>\n\n"
        f"💰 <b>USDT:</b> {user_data['usdt_balance']:.2f}\n"
        f"🎯 <b>Сигналы:</b> {user_data['signals_balance']} шт.\n\n"
        f"Выберите действие:"
    )

    await message.answer(balance_text, reply_markup=get_balance_menu(), parse_mode="HTML")


@router.callback_query(F.data == "back_to_balance")
async def back_to_balance_callback(callback: types.CallbackQuery):
    user_data = await get_user(callback.from_user.id)
    if not user_data:
        await callback.message.edit_text("❌ Ошибка при получении данных.")
        return

    balance_text = (
        f"💼 <b>Ваш баланс:</b>\n\n"
        f"💰 <b>USDT:</b> {user_data['usdt_balance']:.2f}\n"
        f"🎯 <b>Сигналы:</b> {user_data['signals_balance']} шт.\n\n"
        f"Выберите действие:"
    )

    await callback.message.edit_text(balance_text, reply_markup=get_balance_menu(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "deposit_usdt")
async def deposit_usdt_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 Выберите сумму для пополнения USDT:",
        reply_markup=get_usdt_deposit_amounts_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_usdt_"))
async def deposit_usdt_amount_callback(callback: types.CallbackQuery, state: FSMContext):
    # Extract amount from callback data
    amount = float(callback.data.split("_")[-1])

    # Store amount in state
    await state.update_data(usdt_deposit_amount=amount)

    # Here we would integrate with a payment provider
    # For now, we'll simulate a payment link
    payment_text = (
        f"💰 Вы выбрали пополнение на <b>{amount} USDT</b>\n\n"
        f"Для проведения платежа нажмите на кнопку ниже.\n\n"
        f"После подтверждения оплаты USDT будут автоматически зачислены на ваш баланс."
    )

    # Simulate payment process - in real implementation, redirect to payment provider
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_back_to_balance_keyboard(),
        parse_mode="HTML"
    )

    # For demonstration, let's simulate successful payment
    # In a real implementation, this would be handled by a webhook from the payment provider
    await state.set_state(DepositStates.waiting_for_payment)

    # Simulate payment processing for demo
    # In real implementation, remove this and use webhook callback
    result = await add_usdt_balance(callback.from_user.id, amount)
    if result and result.get("success"):
        user_data = await get_user(callback.from_user.id)
        await callback.message.answer(
            f"✅ <b>Пополнение успешно!</b>\n\n"
            f"💰 <b>USDT баланс:</b> {user_data['usdt_balance']:.2f}\n"
            f"🎯 <b>Сигналы:</b> {user_data['signals_balance']} шт.",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()

    await callback.answer()


@router.callback_query(F.data == "buy_signals")
async def buy_signals_callback(callback: types.CallbackQuery):
    user_data = await get_user(callback.from_user.id)
    if not user_data:
        await callback.message.edit_text("❌ Ошибка при получении данных.")
        return

    buy_signals_text = (
        f"🛒 <b>Покупка сигналов</b>\n\n"
        f"💰 <b>Ваш USDT баланс:</b> {user_data['usdt_balance']:.2f}\n"
        f"🎯 <b>Текущие сигналы:</b> {user_data['signals_balance']} шт.\n\n"
        f"Выберите действие:"
    )

    await callback.message.edit_text(
        buy_signals_text,
        reply_markup=get_buy_signals_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "select_package")
async def select_package_callback(callback: types.CallbackQuery):
    user_data = await get_user(callback.from_user.id)
    if not user_data:
        await callback.message.edit_text("❌ Ошибка при получении данных.")
        return

    package_text = (
        f"📦 <b>Выберите пакет сигналов:</b>\n\n"
        f"💰 <b>Ваш USDT баланс:</b> {user_data['usdt_balance']:.2f}\n\n"
        f"Доступные пакеты:"
    )

    await callback.message.edit_text(
        package_text,
        reply_markup=get_packages_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("package_"))
async def package_selection_callback(callback: types.CallbackQuery):
    # Extract package ID from callback data
    package_id = int(callback.data.split("_")[1])

    # Find package details
    package = None
    for pkg in settings.DEFAULT_PACKAGES:
        if pkg["id"] == package_id:
            package = pkg
            break

    if not package:
        await callback.message.edit_text("❌ Пакет не найден.")
        return

    user_data = await get_user(callback.from_user.id)
    if not user_data:
        await callback.message.edit_text("❌ Ошибка при получении данных.")
        return

    # Check if user has enough USDT
    if user_data['usdt_balance'] < package['price']:
        insufficient_text = (
            f"❌ <b>Недостаточно средств</b>\n\n"
            f"💰 <b>Ваш USDT баланс:</b> {user_data['usdt_balance']:.2f}\n"
            f"💳 <b>Стоимость пакета:</b> {package['price']:.2f} USDT\n"
            f"📊 <b>Не хватает:</b> {package['price'] - user_data['usdt_balance']:.2f} USDT\n\n"
            f"Пополните баланс для покупки пакета."
        )
        await callback.message.edit_text(
            insufficient_text,
            reply_markup=get_buy_signals_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Show package confirmation
    confirm_text = (
        f"📦 <b>Подтверждение покупки</b>\n\n"
        f"🎯 <b>Пакет:</b> {package['name']}\n"
        f"📊 <b>Количество сигналов:</b> {package['signals_count']} шт.\n"
        f"💰 <b>Стоимость:</b> {package['price']:.2f} USDT\n\n"
        f"💳 <b>Ваш USDT баланс:</b> {user_data['usdt_balance']:.2f}\n"
        f"💸 <b>Останется после покупки:</b> {user_data['usdt_balance'] - package['price']:.2f} USDT\n\n"
        f"Подтвердите покупку:"
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_package_confirm_keyboard(package_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_package_"))
async def confirm_package_callback(callback: types.CallbackQuery):
    # Extract package ID from callback data
    package_id = int(callback.data.split("_")[2])

    # Purchase signals
    result = await purchase_signals(callback.from_user.id, package_id)

    if result and result.get("success"):
        success_text = (
            f"✅ <b>Покупка успешна!</b>\n\n"
            f"📦 <b>Пакет:</b> {result['package']}\n"
            f"🎯 <b>Добавлено сигналов:</b> {result['signals_added']} шт.\n\n"
            f"💰 <b>USDT баланс:</b> {result['usdt_balance']:.2f}\n"
            f"🎯 <b>Сигналы:</b> {result['signals_balance']} шт."
        )

        await callback.message.edit_text(
            success_text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    else:
        error_message = result.get("error", "Неизвестная ошибка") if result else "Ошибка сервера"
        await callback.message.edit_text(
            f"❌ <b>Ошибка при покупке:</b> {error_message}",
            reply_markup=get_buy_signals_menu(),
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_menu()
    )
    await callback.answer()