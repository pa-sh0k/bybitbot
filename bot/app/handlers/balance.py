from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import aiohttp
from datetime import datetime

from config import settings
from keyboards import (
    get_main_menu, get_balance_menu, get_deposit_amounts_keyboard,
    get_cancel_keyboard, get_back_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


# States
class DepositStates(StatesGroup):
    waiting_for_amount = State()
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


# Helper function to add balance to user
async def add_user_balance(telegram_id: int, amount: int):
    try:
        async with aiohttp.ClientSession() as session:
            params = {"amount": amount}
            async with session.post(f"{settings.API_URL}/api/users/{telegram_id}/add_balance",
                                    params=params) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error adding balance: {e}")
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

    # Show balance
    balance_text = (
        f"💼 Ваш текущий баланс: {user_data['balance']} сигналов\n\n"
        f"Для пополнения баланса нажмите кнопку ниже:"
    )

    await message.answer(balance_text, reply_markup=get_balance_menu())


@router.callback_query(F.data == "deposit")
async def deposit_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 Выберите сумму для пополнения:",
        reply_markup=get_deposit_amounts_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_amount_"))
async def deposit_amount_callback(callback: types.CallbackQuery, state: FSMContext):
    # Extract amount from callback data
    amount = float(callback.data.split("_")[-1])

    # Store amount in state
    await state.update_data(deposit_amount=amount)

    # Here we would integrate with a payment provider
    # For now, we'll simulate a payment link
    payment_text = (
        f"💰 Вы выбрали пополнение на {amount} USDT\n\n"
        f"Для проведения платежа нажмите на кнопку ниже.\n\n"
        f"После подтверждения оплаты сигналы будут автоматически зачислены на ваш баланс."
    )

    # Simulate payment process - in real implementation, redirect to payment provider
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_back_keyboard()
    )

    # For demonstration, let's simulate successful payment
    # In a real implementation, this would be handled by a webhook from the payment provider
    await state.set_state(DepositStates.waiting_for_payment)

    # Simulate payment processing for demo
    # In real implementation, remove this and use webhook callback
    result = await add_user_balance(callback.from_user.id, int(amount))
    if result and result.get("success"):
        user_data = await get_user(callback.from_user.id)
        await callback.message.answer(
            f"✅ Средства успешно зачислены!\n"
            f"Ваш баланс: {user_data['balance']} сигналов",
            reply_markup=get_main_menu()
        )
        await state.clear()

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