from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import logging
import aiohttp
from datetime import datetime

from app.config import settings
from app.keyboards import get_main_menu, get_admin_menu

router = Router()
logger = logging.getLogger(__name__)


# Helper function to register user with API
async def register_user(user: types.User):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
            async with session.post(f"{settings.API_URL}/api/users/", json=payload) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        return None


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


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    # Get or create user
    user_data = await get_user(message.from_user.id)
    if not user_data:
        user_data = await register_user(message.from_user)
        if not user_data:
            await message.answer(
                "❌ Ошибка при регистрации. Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )
            return

    # Check if user is admin
    is_admin = message.from_user.id in settings.ADMIN_USER_IDS

    # Welcome message
    welcome_text = (
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        f"Это бот для получения торговых сигналов с Bybit.\n\n"
        f"💰 Ваш баланс: {user_data['balance']} сигналов\n\n"
        f"Используйте меню ниже для навигации:"
    )

    # Choose keyboard based on user role
    keyboard = get_admin_menu() if is_admin else get_main_menu()

    await message.answer(welcome_text, reply_markup=keyboard)


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    # Check if user is admin
    if message.from_user.id in settings.ADMIN_USER_IDS:
        await message.answer(
            "🔑 Вы вошли в режим администратора",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            "⛔ У вас нет доступа к этой команде."
        )


@router.message(F.text == "🔙 Обычное меню")
async def back_to_user_menu(message: types.Message):
    # Check if user is admin
    if message.from_user.id in settings.ADMIN_USER_IDS:
        await message.answer(
            "✅ Вы вернулись в обычное меню",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "⛔ У вас нет доступа к этой команде."
        )