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
        "🆘 Поддержка\n\n"
        "Если у вас возникли вопросы или проблемы, вы можете обратиться к администратору.",
        reply_markup=get_support_keyboard()
    )


@router.callback_query(F.data == "contact_admin")
async def contact_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Напишите ваше сообщение для администратора:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(SupportStates.waiting_for_message)
    await callback.answer()


@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: types.Message, state: FSMContext):
    # Save message to state
    await state.update_data(support_message=message.text)

    # Forward message to admin(s)
    for admin_id in settings.ADMIN_USER_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"📩 Новое сообщение от пользователя {message.from_user.full_name} (ID: {message.from_user.id}):\n\n"
                f"{message.text}"
            )
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")

    # Confirm receipt
    await message.answer(
        "✅ Ваше сообщение отправлено администратору. Мы ответим вам в ближайшее время.",
        reply_markup=get_main_menu()
    )

    # Clear state
    await state.clear()


@router.callback_query(F.data == "faq")
async def faq_callback(callback: types.CallbackQuery):
    faq_text = (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "<b>Как работают сигналы?</b>\n"
        "Сигналы формируются на основе торговых операций профессиональных трейдеров на платформе Bybit. "
        "Когда трейдер открывает или закрывает позицию, вы получаете уведомление.\n\n"

        "<b>Сколько стоит один сигнал?</b>\n"
        "Стоимость одного сигнала составляет 1 USDT. Вы можете приобрести пакеты сигналов с дополнительной скидкой.\n\n"

        "<b>Как пополнить баланс?</b>\n"
        "Нажмите на кнопку \"💼 Баланс\", затем \"💳 Пополнить баланс\" и следуйте инструкциям.\n\n"

        "<b>Могу ли я получить возврат средств?</b>\n"
        "Возврат средств не предусмотрен после приобретения сигналов.\n\n"

        "<b>Как связаться с поддержкой?</b>\n"
        "Используйте раздел \"🆘 Поддержка\" для отправки сообщения администратору."
    )

    await callback.message.edit_text(
        faq_text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


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