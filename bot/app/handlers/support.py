from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
from config import settings
from keyboards import get_support_keyboard, get_cancel_keyboard, get_back_keyboard, get_main_menu

router = Router()
logger = logging.getLogger(__name__)


# States
class SupportStates(StatesGroup):
    waiting_for_message = State()


@router.message(F.text == "🆘 Поддержка")
async def show_support(message: types.Message):
    await message.answer(
        "По вопросам поддержки пишите сюда",
        reply_markup=get_support_keyboard()
    )


# Reply to user from admin
@router.message(F.text.startswith("/reply"))
async def admin_reply(message: types.Message):
    # Check if sender is admin
    if message.from_user.id not in settings.ADMIN_USER_IDS:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    try:
        # Format: /reply USER_ID message text
        parts = message.text.split(" ", 2)
        if len(parts) < 3:
            await message.answer("❌ Неверный формат. Используйте: /reply USER_ID текст_сообщения")
            return

        user_id = int(parts[1])
        reply_text = parts[2]

        # Send reply to user
        await message.bot.send_message(
            user_id,
            f"📩 <b>Ответ от администратора:</b>\n\n{reply_text}",
            parse_mode="HTML"
        )

        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}")

    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке сообщения: {e}")


@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=get_main_menu()
    )
    await callback.answer()